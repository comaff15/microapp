from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.acl import can_write
from app.domain import validate_transition
from app.broker import publisher
from app.deps import get_current_user_email, get_db
from app.schemas import TaskCreate, TaskPublic, TaskUpdate

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


@router.post("", response_model=TaskPublic, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: int,
    payload: TaskCreate,
    owner_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=owner_email)
    if my_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    if not can_write(my_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only project role")

    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task = await crud.create_task(
        db,
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        tags=payload.tags,
    )

    try:
        await publisher.publish(
            "task.created",
            {
                "task_id": task.id,
                "project_id": project_id,
                "owner_email": owner_email,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "tags": [t.name for t in task.tags],
            },
        )
    except Exception:
        pass

    return TaskPublic(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        tags=[t.name for t in task.tags],
        is_archived=task.is_archived,
    )


@router.get("", response_model=list[TaskPublic])
async def list_tasks(
    project_id: int,
    status_filter: str | None = None,
    priority: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    owner_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=owner_email)
    if my_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")

    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    tasks = await crud.list_tasks(
        db,
        project_id=project_id,
        status=status_filter,
        priority=priority,
        q=q,
        tag=tag,
        include_archived=include_archived,
    )
    return [
        TaskPublic(
            id=t.id,
            project_id=t.project_id,
            title=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            tags=[x.name for x in t.tags],
            is_archived=t.is_archived,
        )
        for t in tasks
    ]


@router.get("/{task_id}", response_model=TaskPublic)
async def get_task(
    project_id: int,
    task_id: int,
    owner_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=owner_email)
    if my_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")

    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task = await crud.get_task(db, task_id=task_id, project_id=project_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return TaskPublic(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        tags=[t.name for t in task.tags],
        is_archived=task.is_archived,
    )


@router.patch("/{task_id}", response_model=TaskPublic)
async def patch_task(
    project_id: int,
    task_id: int,
    payload: TaskUpdate,
    owner_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=owner_email)
    if my_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    if not can_write(my_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only project role")

    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task = await crud.get_task(db, task_id=task_id, project_id=project_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Validate transitions early to return 400 instead of 500.
    if payload.status is not None:
        try:
            validate_transition(task.status, payload.status)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        task = await crud.update_task(
            db,
            task=task,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            tags=payload.tags,
            is_archived=payload.is_archived,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    event_key = "task.updated"
    if payload.status == "done":
        event_key = "task.completed"
    if payload.is_archived is True:
        event_key = "task.archived"
    if payload.is_archived is False:
        event_key = "task.restored"

    try:
        await publisher.publish(
            event_key,
            {
                "task_id": task.id,
                "project_id": project_id,
                "owner_email": owner_email,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "tags": [x.name for x in task.tags],
                "is_archived": task.is_archived,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        pass

    return TaskPublic(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        tags=[x.name for x in task.tags],
        is_archived=task.is_archived,
    )


@router.post("/{task_id}/archive", response_model=TaskPublic)
async def archive_task(
    project_id: int,
    task_id: int,
    owner_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=owner_email)
    if my_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    if not can_write(my_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only project role")

    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task = await crud.get_task(db, task_id=task_id, project_id=project_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task = await crud.update_task(db, task=task, is_archived=True)

    await publisher.publish(
        "task.archived",
        {
            "task_id": task.id,
            "project_id": project_id,
            "owner_email": owner_email,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "tags": [x.name for x in task.tags],
            "is_archived": task.is_archived,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )

    return TaskPublic(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        tags=[x.name for x in task.tags],
        is_archived=task.is_archived,
    )


@router.post("/{task_id}/restore", response_model=TaskPublic)
async def restore_task(
    project_id: int,
    task_id: int,
    owner_email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    my_role = await crud.get_my_project_role(db, project_id=project_id, user_email=owner_email)
    if my_role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    if not can_write(my_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only project role")

    project = await crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task = await crud.get_task(db, task_id=task_id, project_id=project_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task = await crud.update_task(db, task=task, is_archived=False)

    await publisher.publish(
        "task.restored",
        {
            "task_id": task.id,
            "project_id": project_id,
            "owner_email": owner_email,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "tags": [x.name for x in task.tags],
            "is_archived": task.is_archived,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )

    return TaskPublic(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        tags=[x.name for x in task.tags],
        is_archived=task.is_archived,
    )
