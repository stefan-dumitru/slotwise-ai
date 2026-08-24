from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..auth_utils import get_current_user, require_role
from ..database import get_db

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.get("/me", response_model=list[schemas.CustomerAppointmentOut])
def my_appointments(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    appointments = crud.get_user_appointments(db, current_user.id)
    return [
        {
            "id": a.id,
            "business_name": a.business.name,
            "service_name": a.service.name,
            "staff_name": a.staff.full_name,
            "start_time": a.start_time,
            "end_time": a.end_time,
            "status": a.status,
            "has_review": a.review is not None,
        }
        for a in appointments
    ]


@router.post("", response_model=schemas.AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(
    payload: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return crud.create_appointment(db, current_user.id, payload.service_id, payload.staff_id, payload.start_time)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{appointment_id}/cancel", response_model=schemas.AppointmentOut)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return crud.cancel_appointment(db, appointment_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{appointment_id}/status", response_model=schemas.AppointmentOut)
def update_appointment_status(
    appointment_id: int,
    payload: schemas.AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("business_owner", "admin")),
):
    try:
        return crud.update_appointment_status(
            db, appointment_id, current_user.id, payload.status, is_admin=current_user.role == "admin"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{appointment_id}/review", response_model=schemas.ReviewOut, status_code=status.HTTP_201_CREATED)
def leave_review(
    appointment_id: int,
    payload: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        review = crud.create_review(db, appointment_id, current_user.id, payload.rating, payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "id": review.id,
        "appointment_id": review.appointment_id,
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at,
        "customer_name": current_user.full_name,
    }
