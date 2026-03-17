from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.deps import get_db, require_admin
from app.schemas import UserAdminUpdate, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserPublic])
async def list_users(limit: int = 200, before_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    users = await crud.list_users(db, limit=limit, before_id=before_id)
    return [UserPublic(id=u.id, email=u.email, role=u.role, is_active=u.is_active) for u in users]


@router.patch("/users/{user_id}", response_model=UserPublic)
async def patch_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    user = await crud.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await crud.update_user_admin(db, user=user, role=payload.role, is_active=payload.is_active)
    return UserPublic(id=user.id, email=user.email, role=user.role, is_active=user.is_active)
