from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.acl import PROJECT_ROLES
from app.deps import get_current_user_email, get_db

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


class MemberCreate(BaseModel):
    user_email: EmailStr
    role: str = "viewer"


class MemberPublic(BaseModel):
    project_id: int
    user_email: EmailStr
    role: str


class TransferOwnershipRequest(BaseModel):
    new_owner_email: EmailStr


@router.get("", response_model=list[MemberPublic])
async def list_members(
    project_id: int,
    me: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    role = await crud.get_my_project_role(db, project_id=project_id, user_email=me)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")

    members = await crud.list_members(db, project_id=project_id)
    return [MemberPublic(project_id=m.project_id, user_email=m.user_email, role=m.role) for m in members]


@router.post("", response_model=MemberPublic, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: int,
    payload: MemberCreate,
    me: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=me)
    if my_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    if payload.role not in PROJECT_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    if payload.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Use transfer ownership endpoint instead of setting owner role directly",
        )

    member = await crud.upsert_member(db, project_id=project_id, user_email=str(payload.user_email), role=payload.role)
    return MemberPublic(project_id=member.project_id, user_email=member.user_email, role=member.role)


@router.delete("/{user_email}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: int,
    user_email: str,
    me: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=me)
    if my_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    if user_email == me:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Owner cannot remove themselves; transfer ownership first",
        )

    target_role = await crud.get_my_project_role(db, project_id=project_id, user_email=user_email)
    if target_role == "owner":
        owners = await crud.count_owners(db, project_id=project_id)
        if owners <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot remove last owner")

    await crud.remove_member(db, project_id=project_id, user_email=user_email)
    return None


@router.post("/transfer", status_code=status.HTTP_204_NO_CONTENT)
async def transfer_ownership(
    project_id: int,
    payload: TransferOwnershipRequest,
    me: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=me)
    if my_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    try:
        await crud.transfer_ownership(
            db,
            project_id=project_id,
            current_owner_email=me,
            new_owner_email=str(payload.new_owner_email),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return None
