from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.schemas.user import UserOut, UserUpdateRole
from backend.core.auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """List all users. Admin only."""
    return db.query(User).all()


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: int,
    body: UserUpdateRole,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """Change a user's role. Admin only."""
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Admins cannot change their own role")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = body.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """Deactivate a user account. Admin only."""
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
