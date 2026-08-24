from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..auth_utils import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/me", response_model=list[schemas.NotificationOut])
def my_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.get_user_notifications(db, current_user.id)


@router.post("/{notification_id}/read", response_model=schemas.NotificationOut)
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return crud.mark_notification_read(db, notification_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    crud.mark_all_notifications_read(db, current_user.id)
