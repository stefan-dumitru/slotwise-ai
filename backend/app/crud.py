from datetime import date, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models

SLOT_STEP = timedelta(minutes=15)


def get_categories(db: Session) -> list[models.Category]:
    return db.query(models.Category).order_by(models.Category.name).all()


def search_services(db: Session, query: str | None = None, category_name: str | None = None, limit: int = 10):
    q = (
        db.query(models.Service)
        .join(models.Business, models.Service.business_id == models.Business.id)
        .filter(models.Service.is_active.is_(True), models.Business.status == "active")
    )
    if category_name:
        q = q.join(models.Category, models.Business.category_id == models.Category.id).filter(
            models.Category.name.ilike(f"%{category_name}%")
        )
    if query:
        like = f"%{query}%"
        q = q.filter(
            or_(
                models.Service.name.ilike(like),
                models.Service.description.ilike(like),
                models.Business.name.ilike(like),
            )
        )
    return q.limit(limit).all()


def get_staff_for_service(db: Session, service: models.Service) -> list[models.Staff]:
    if service.staff_members:
        return service.staff_members
    return db.query(models.Staff).filter(models.Staff.business_id == service.business_id).all()


def _periods_for_day(db: Session, staff_id: int, day: date, schema_dow: int):
    exception = (
        db.query(models.AvailabilityException)
        .filter(models.AvailabilityException.staff_id == staff_id, models.AvailabilityException.exception_date == day)
        .first()
    )
    if exception:
        if exception.is_closed:
            return []
        if exception.start_time and exception.end_time:
            return [(exception.start_time, exception.end_time)]
    rows = (
        db.query(models.WorkingHours)
        .filter(models.WorkingHours.staff_id == staff_id, models.WorkingHours.day_of_week == schema_dow)
        .all()
    )
    return [(row.start_time, row.end_time) for row in rows]


def _overlaps(start: datetime, end: datetime, existing: list[models.Appointment]) -> bool:
    return any(start < appt.end_time and end > appt.start_time for appt in existing)


def compute_available_slots(
    db: Session,
    service: models.Service,
    date_from: date,
    date_to: date,
    staff_id: int | None = None,
    limit: int = 40,
) -> list[dict]:
    duration = timedelta(minutes=service.duration_minutes)
    candidate_staff = [staff_id] if staff_id else [s.id for s in get_staff_for_service(db, service)]

    slots: list[dict] = []
    current_day = date_from
    while current_day <= date_to and len(slots) < limit:
        schema_dow = (current_day.weekday() + 1) % 7  # our schema: 0=Sunday ... 6=Saturday
        for sid in candidate_staff:
            periods = _periods_for_day(db, sid, current_day, schema_dow)
            if not periods:
                continue
            existing = (
                db.query(models.Appointment)
                .filter(
                    models.Appointment.staff_id == sid,
                    models.Appointment.status.in_(["pending", "confirmed"]),
                )
                .all()
            )
            for start_t, end_t in periods:
                slot_start = datetime.combine(current_day, start_t)
                period_end = datetime.combine(current_day, end_t)
                while slot_start + duration <= period_end and len(slots) < limit:
                    slot_end = slot_start + duration
                    if slot_start > datetime.now() and not _overlaps(slot_start, slot_end, existing):
                        staff = db.get(models.Staff, sid)
                        slots.append(
                            {
                                "staff_id": sid,
                                "staff_name": staff.full_name,
                                "start_time": slot_start,
                                "end_time": slot_end,
                            }
                        )
                    slot_start += SLOT_STEP
        current_day += timedelta(days=1)
    return slots


def is_slot_free(db: Session, staff_id: int, start_time: datetime, end_time: datetime) -> bool:
    conflict = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.staff_id == staff_id,
            models.Appointment.status.in_(["pending", "confirmed"]),
            models.Appointment.start_time < end_time,
            models.Appointment.end_time > start_time,
        )
        .first()
    )
    return conflict is None


def _fmt(dt: datetime) -> str:
    return dt.strftime("%b %d, %Y at %I:%M %p")


def create_notification(
    db: Session, user_id: int, notif_type: str, message: str, appointment_id: int | None = None
) -> models.Notification:
    notification = models.Notification(
        user_id=user_id, appointment_id=appointment_id, type=notif_type, message=message, is_read=False
    )
    db.add(notification)
    db.commit()
    return notification


def create_appointment(db: Session, customer_id: int, service_id: int, staff_id: int, start_time: datetime) -> models.Appointment:
    service = db.get(models.Service, service_id)
    if not service:
        raise ValueError("Service not found")
    staff = db.get(models.Staff, staff_id)
    if not staff or staff.business_id != service.business_id:
        raise ValueError("Staff does not belong to this service's business")

    end_time = start_time + timedelta(minutes=service.duration_minutes)
    # Best-effort check-then-insert; a production system would add row locking
    # (SELECT ... FOR UPDATE) to fully close the race window under concurrent bookings.
    if not is_slot_free(db, staff_id, start_time, end_time):
        raise ValueError("That slot is no longer available")

    appointment = models.Appointment(
        customer_id=customer_id,
        business_id=staff.business_id,
        service_id=service_id,
        staff_id=staff_id,
        start_time=start_time,
        end_time=end_time,
        status="confirmed",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    customer = db.get(models.User, customer_id)
    business = staff.business
    create_notification(
        db,
        customer_id,
        "booking_confirmation",
        f"Your {service.name} appointment at {business.name} is confirmed for {_fmt(start_time)}.",
        appointment_id=appointment.id,
    )
    create_notification(
        db,
        business.owner_id,
        "booking_confirmation",
        f"New booking: {customer.full_name} booked {service.name} for {_fmt(start_time)}.",
        appointment_id=appointment.id,
    )
    return appointment


def get_user_appointments(db: Session, user_id: int) -> list[models.Appointment]:
    return (
        db.query(models.Appointment)
        .filter(models.Appointment.customer_id == user_id)
        .order_by(models.Appointment.start_time.desc())
        .all()
    )


def cancel_appointment(db: Session, appointment_id: int, user_id: int, reason: str | None = None) -> models.Appointment:
    appointment = db.get(models.Appointment, appointment_id)
    if not appointment or appointment.customer_id != user_id:
        raise ValueError("Appointment not found")
    appointment.status = "cancelled"
    appointment.cancellation_reason = reason
    db.commit()
    db.refresh(appointment)

    create_notification(
        db,
        appointment.business.owner_id,
        "cancellation",
        f"{appointment.customer.full_name} cancelled their {appointment.service.name} appointment "
        f"for {_fmt(appointment.start_time)}.",
        appointment_id=appointment.id,
    )
    return appointment


def get_business_appointments(db: Session, business_id: int) -> list[models.Appointment]:
    return (
        db.query(models.Appointment)
        .filter(models.Appointment.business_id == business_id)
        .order_by(models.Appointment.start_time.desc())
        .all()
    )


def update_appointment_status(
    db: Session, appointment_id: int, owner_id: int, new_status: str, is_admin: bool = False
) -> models.Appointment:
    appointment = db.get(models.Appointment, appointment_id)
    if not appointment:
        raise ValueError("Appointment not found")
    if not is_admin and appointment.business.owner_id != owner_id:
        raise ValueError("You do not own this business")
    appointment.status = new_status
    db.commit()
    db.refresh(appointment)

    status_messages = {
        "completed": ("general", f"Your {appointment.service.name} appointment for {_fmt(appointment.start_time)} was marked completed."),
        "no_show": ("general", f"Your {appointment.service.name} appointment for {_fmt(appointment.start_time)} was marked as a no-show."),
        "cancelled": ("cancellation", f"{appointment.business.name} cancelled your {appointment.service.name} appointment for {_fmt(appointment.start_time)}."),
        "confirmed": ("general", f"Your {appointment.service.name} appointment for {_fmt(appointment.start_time)} is confirmed."),
    }
    notif_type, message = status_messages[new_status]
    create_notification(db, appointment.customer_id, notif_type, message, appointment_id=appointment.id)
    return appointment


def update_business(db: Session, business_id: int, updates: dict) -> models.Business:
    business = db.get(models.Business, business_id)
    if not business:
        raise ValueError("Business not found")
    for key, value in updates.items():
        setattr(business, key, value)
    db.commit()
    db.refresh(business)
    return business


def create_review(db: Session, appointment_id: int, customer_id: int, rating: int, comment: str | None) -> models.Review:
    appointment = db.get(models.Appointment, appointment_id)
    if not appointment or appointment.customer_id != customer_id:
        raise ValueError("Appointment not found")
    if appointment.status != "completed":
        raise ValueError("You can only review a completed appointment")
    if appointment.review is not None:
        raise ValueError("This appointment has already been reviewed")

    review = models.Review(
        appointment_id=appointment_id,
        customer_id=customer_id,
        business_id=appointment.business_id,
        rating=rating,
        comment=comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_business_reviews(db: Session, business_id: int) -> list[tuple[models.Review, str]]:
    return (
        db.query(models.Review, models.User.full_name)
        .join(models.User, models.Review.customer_id == models.User.id)
        .filter(models.Review.business_id == business_id)
        .order_by(models.Review.created_at.desc(), models.Review.id.desc())
        .all()
    )


def get_user_notifications(db: Session, user_id: int) -> list[models.Notification]:
    # created_at has only 1-second resolution, and several notifications can be inserted
    # within the same request (e.g. booking confirms both the customer and the owner), so
    # id is needed as a tiebreaker to keep "latest first" actually deterministic.
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.created_at.desc(), models.Notification.id.desc())
        .all()
    )


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> models.Notification:
    notification = db.get(models.Notification, notification_id)
    if not notification or notification.user_id != user_id:
        raise ValueError("Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, user_id: int) -> None:
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id, models.Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()


def list_all_users(db: Session) -> list[models.User]:
    return db.query(models.User).order_by(models.User.id).all()


def update_user_role(db: Session, user_id: int, new_role: str) -> models.User:
    user = db.get(models.User, user_id)
    if not user:
        raise ValueError("User not found")
    user.role = new_role
    db.commit()
    db.refresh(user)
    return user


def list_all_businesses(db: Session) -> list[models.Business]:
    return db.query(models.Business).order_by(models.Business.id).all()


def update_business_status(db: Session, business_id: int, new_status: str) -> models.Business:
    business = db.get(models.Business, business_id)
    if not business:
        raise ValueError("Business not found")
    business.status = new_status
    db.commit()
    db.refresh(business)
    return business
