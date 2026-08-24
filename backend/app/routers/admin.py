from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..auth_utils import require_role
from ..database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(require_role("admin"))):
    return crud.list_all_users(db)


@router.patch("/users/{user_id}/role", response_model=schemas.UserOut)
def set_user_role(
    user_id: int,
    payload: schemas.UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    if user_id == current_user.id and payload.role != "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove your own admin role")
    try:
        return crud.update_user_role(db, user_id, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/businesses", response_model=list[schemas.AdminBusinessOut])
def list_businesses(db: Session = Depends(get_db), _: models.User = Depends(require_role("admin"))):
    businesses = crud.list_all_businesses(db)
    return [
        {
            "id": b.id,
            "name": b.name,
            "status": b.status,
            "owner_name": b.owner.full_name,
            "owner_email": b.owner.email,
            "category_name": b.category.name if b.category else None,
        }
        for b in businesses
    ]


@router.patch("/businesses/{business_id}/status", response_model=schemas.BusinessOut)
def set_business_status(
    business_id: int,
    payload: schemas.BusinessStatusUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("admin")),
):
    try:
        return crud.update_business_status(db, business_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/categories", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("admin")),
):
    if db.query(models.Category).filter(models.Category.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category already exists")
    category = models.Category(name=payload.name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("admin")),
):
    category = db.get(models.Category, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(category)
    db.commit()
