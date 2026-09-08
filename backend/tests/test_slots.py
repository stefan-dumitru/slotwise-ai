from datetime import date, datetime, time, timedelta

import pytest

from app import crud, models


def test_slots_available_on_a_working_day(db_session, seed_business):
    service = seed_business["service"]
    target_date = date.today() + timedelta(days=3)

    slots = crud.compute_available_slots(db_session, service, target_date, target_date, limit=50)

    assert len(slots) > 0
    assert slots[0]["start_time"].time() == time(9, 0)


def test_booked_slot_disappears_from_availability(db_session, seed_business):
    service = seed_business["service"]
    staff = seed_business["staff"]
    target_date = date.today() + timedelta(days=3)

    slots_before = crud.compute_available_slots(db_session, service, target_date, target_date, limit=50)
    first_slot_start = slots_before[0]["start_time"]

    customer = models.User(full_name="Customer", email="slots-customer@slotwise-tests.dev", password_hash="x", role="customer")
    db_session.add(customer)
    db_session.commit()

    crud.create_appointment(db_session, customer.id, service.id, staff.id, first_slot_start)

    slots_after = crud.compute_available_slots(db_session, service, target_date, target_date, limit=50)
    assert not any(s["start_time"] == first_slot_start for s in slots_after)


def test_double_booking_the_same_slot_raises(db_session, seed_business):
    service = seed_business["service"]
    staff = seed_business["staff"]
    target_date = date.today() + timedelta(days=3)
    start_time = datetime.combine(target_date, time(9, 0))

    customer = models.User(full_name="Customer", email="double-book@slotwise-tests.dev", password_hash="x", role="customer")
    db_session.add(customer)
    db_session.commit()

    crud.create_appointment(db_session, customer.id, service.id, staff.id, start_time)

    with pytest.raises(ValueError):
        crud.create_appointment(db_session, customer.id, service.id, staff.id, start_time)


def test_no_slots_for_staff_with_no_working_hours(db_session, seed_business):
    business = seed_business["business"]
    service = seed_business["service"]
    target_date = date.today() + timedelta(days=3)

    idle_staff = models.Staff(business_id=business.id, full_name="Idle Staff")
    db_session.add(idle_staff)
    db_session.commit()

    slots = crud.compute_available_slots(db_session, service, target_date, target_date, staff_id=idle_staff.id, limit=50)
    assert slots == []
