from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..auth_utils import get_current_user, require_role
from ..database import get_db

router = APIRouter(prefix="/api", tags=["businesses"])


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).order_by(models.Category.name).all()


@router.get("/businesses", response_model=list[schemas.BusinessOut])
def list_businesses(category_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Business).filter(models.Business.status == "active")
    if category_id is not None:
        query = query.filter(models.Business.category_id == category_id)
    return query.order_by(models.Business.name).all()


# Registered before /businesses/{business_id} so "mine" isn't parsed as an id.
@router.get("/businesses/mine", response_model=list[schemas.BusinessOut])
def list_my_businesses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    query = db.query(models.Business)
    if current_user.role != "admin":
        query = query.filter(models.Business.owner_id == current_user.id)
    return query.order_by(models.Business.name).all()


@router.get("/businesses/{business_id}", response_model=schemas.BusinessOut)
def get_business(business_id: int, db: Session = Depends(get_db)):
    business = db.get(models.Business, business_id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return business


@router.post("/businesses", response_model=schemas.BusinessOut, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: schemas.BusinessCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    business = models.Business(owner_id=current_user.id, **payload.model_dump())
    db.add(business)
    db.flush()

    # Every business gets a default staff record representing the owner, so a solo
    # provider can be scheduled without needing to explicitly add "staff".
    default_staff = models.Staff(business_id=business.id, user_id=current_user.id, full_name=current_user.full_name)
    db.add(default_staff)

    db.commit()
    db.refresh(business)
    return business


def _get_owned_business(db: Session, business_id: int, current_user: models.User) -> models.Business:
    business = db.get(models.Business, business_id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    if business.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this business")
    return business


@router.patch("/businesses/{business_id}", response_model=schemas.BusinessOut)
def update_business(
    business_id: int,
    payload: schemas.BusinessUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    _get_owned_business(db, business_id, current_user)
    return crud.update_business(db, business_id, payload.model_dump(exclude_unset=True))


@router.get("/businesses/{business_id}/services", response_model=list[schemas.ServiceOut])
def list_services(business_id: int, db: Session = Depends(get_db)):
    return db.query(models.Service).filter(models.Service.business_id == business_id, models.Service.is_active.is_(True)).all()


@router.get("/businesses/{business_id}/reviews", response_model=list[schemas.ReviewOut])
def list_reviews(business_id: int, db: Session = Depends(get_db)):
    rows = crud.get_business_reviews(db, business_id)
    return [
        {
            "id": review.id,
            "appointment_id": review.appointment_id,
            "rating": review.rating,
            "comment": review.comment,
            "created_at": review.created_at,
            "customer_name": customer_name,
        }
        for review, customer_name in rows
    ]


@router.post("/businesses/{business_id}/services", response_model=schemas.ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    business_id: int,
    payload: schemas.ServiceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    business = _get_owned_business(db, business_id, current_user)
    service = models.Service(business_id=business.id, **payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/businesses/{business_id}/staff", response_model=list[schemas.StaffOut])
def list_staff(business_id: int, db: Session = Depends(get_db)):
    return db.query(models.Staff).filter(models.Staff.business_id == business_id).all()


@router.post("/businesses/{business_id}/staff", response_model=schemas.StaffOut, status_code=status.HTTP_201_CREATED)
def add_staff(
    business_id: int,
    payload: schemas.StaffCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    business = _get_owned_business(db, business_id, current_user)
    staff = models.Staff(business_id=business.id, full_name=payload.full_name)
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


def _get_owned_staff(db: Session, staff_id: int, current_user: models.User) -> models.Staff:
    staff = db.get(models.Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    _get_owned_business(db, staff.business_id, current_user)
    return staff


@router.get("/staff/{staff_id}/working-hours", response_model=list[schemas.WorkingHoursOut])
def list_working_hours(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    _get_owned_staff(db, staff_id, current_user)
    return (
        db.query(models.WorkingHours)
        .filter(models.WorkingHours.staff_id == staff_id)
        .order_by(models.WorkingHours.day_of_week, models.WorkingHours.start_time)
        .all()
    )


@router.post("/staff/{staff_id}/working-hours", response_model=schemas.WorkingHoursOut, status_code=status.HTTP_201_CREATED)
def add_working_hours(
    staff_id: int,
    payload: schemas.WorkingHoursCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    _get_owned_staff(db, staff_id, current_user)

    entry = models.WorkingHours(
        staff_id=staff_id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/working-hours/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_working_hours(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    entry = db.get(models.WorkingHours, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Working hours entry not found")
    _get_owned_staff(db, entry.staff_id, current_user)
    db.delete(entry)
    db.commit()


@router.get("/businesses/{business_id}/appointments", response_model=list[schemas.OwnerAppointmentOut])
def list_business_appointments(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    business = _get_owned_business(db, business_id, current_user)
    appointments = crud.get_business_appointments(db, business.id)
    return [
        {
            "id": a.id,
            "start_time": a.start_time,
            "end_time": a.end_time,
            "status": a.status,
            "cancellation_reason": a.cancellation_reason,
            "customer_name": a.customer.full_name,
            "customer_email": a.customer.email,
            "service_name": a.service.name,
            "staff_name": a.staff.full_name,
        }
        for a in appointments
    ]
