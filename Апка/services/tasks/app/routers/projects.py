from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache import cache_delete, cache_get, cache_set
from app.deps import get_current_user_email, get_db
from app.schemas import ProjectCreate, ProjectPublic

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    owner_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    project = await crud.create_project(db, name=payload.name, owner_email=owner_email)
    await cache_delete(f"projects:{owner_email}")
    return ProjectPublic(id=project.id, name=project.name, owner_email=project.owner_email)


@router.get("", response_model=list[ProjectPublic])
async def list_projects(
    user_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    key = f"projects:{user_email}"
    cached = await cache_get(key)
    if cached is not None:
        return [ProjectPublic(**p) for p in cached["items"]]

    items = await crud.list_projects(db, user_email=user_email)
    result = [ProjectPublic(id=p.id, name=p.name, owner_email=p.owner_email) for p in items]
    await cache_set(key, {"items": [r.model_dump() for r in result]}, ttl_seconds=15)
    return result


@router.get("/{project_id}", response_model=ProjectPublic)
async def get_project(
    project_id: int,
    user_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    role = await crud.get_my_project_role(db, project_id=project_id, user_email=user_email)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")

    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectPublic(id=project.id, name=project.name, owner_email=project.owner_email)
