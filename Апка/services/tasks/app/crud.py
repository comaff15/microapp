from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectMember, Tag, Task
from app.domain import validate_transition
from datetime import datetime, timezone


async def create_project(session: AsyncSession, *, name: str, owner_email: str) -> Project:
    project = Project(name=name, owner_email=owner_email)
    session.add(project)
    await session.flush()
    session.add(ProjectMember(project_id=project.id, user_email=owner_email, role="owner"))
    await session.commit()
    await session.refresh(project)
    return project


async def get_my_project_role(session: AsyncSession, *, project_id: int, user_email: str) -> str | None:
    res = await session.execute(
        select(ProjectMember.role).where(ProjectMember.project_id == project_id).where(ProjectMember.user_email == user_email)
    )
    return res.scalar_one_or_none()


async def list_members(session: AsyncSession, *, project_id: int) -> list[ProjectMember]:
    res = await session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id).order_by(ProjectMember.user_email.asc())
    )
    return list(res.scalars().all())


async def upsert_member(session: AsyncSession, *, project_id: int, user_email: str, role: str) -> ProjectMember:
    res = await session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id).where(ProjectMember.user_email == user_email)
    )
    member = res.scalar_one_or_none()
    if member is None:
        member = ProjectMember(project_id=project_id, user_email=user_email, role=role)
        session.add(member)
    else:
        member.role = role
 
    await session.commit()
    await session.refresh(member)
    return member


async def remove_member(session: AsyncSession, *, project_id: int, user_email: str) -> None:
    res = await session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id).where(ProjectMember.user_email == user_email)
    )
    member = res.scalar_one_or_none()
    if member is None:
        return
    await session.delete(member)
    await session.commit()


async def count_owners(session: AsyncSession, *, project_id: int) -> int:
    res = await session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id).where(ProjectMember.role == "owner")
    )
    return len(list(res.scalars().all()))


async def transfer_ownership(
    session: AsyncSession,
    *,
    project_id: int,
    current_owner_email: str,
    new_owner_email: str,
) -> None:
    res_old = await session.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .where(ProjectMember.user_email == current_owner_email)
    )
    old_member = res_old.scalar_one_or_none()

    res_new = await session.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .where(ProjectMember.user_email == new_owner_email)
    )
    new_member = res_new.scalar_one_or_none()

    if old_member is None or old_member.role != "owner":
        raise ValueError("Current user is not an owner")
    if new_member is None:
        raise ValueError("New owner must be an existing project member")

    new_member.role = "owner"
    if new_owner_email != current_owner_email:
        old_member.role = "maintainer"

    await session.commit()


async def list_projects(session: AsyncSession, *, user_email: str) -> list[Project]:
    q = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_email == user_email)
        .order_by(Project.id.desc())
    )
    res = await session.execute(q)
    return list(res.scalars().all())


async def get_project(session: AsyncSession, *, project_id: int) -> Project | None:
    res = await session.execute(select(Project).where(Project.id == project_id))
    return res.scalar_one_or_none()


async def create_task(
    session: AsyncSession,
    *,
    project_id: int,
    title: str,
    description: str | None,
    priority: str,
    tags: list[str] | None = None,
) -> Task:
    task = Task(project_id=project_id, title=title, description=description, priority=priority)
    if tags:
        task.tags = await _get_or_create_tags(session, tags)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    await session.refresh(task, attribute_names=["tags"])
    return task


async def _get_or_create_tags(session: AsyncSession, names: list[str]) -> list[Tag]:
    normalized = []
    for n in names:
        nn = n.strip().lower()
        if nn and nn not in normalized:
            normalized.append(nn)

    if not normalized:
        return []

    res = await session.execute(select(Tag).where(Tag.name.in_(normalized)))
    existing = {t.name: t for t in res.scalars().all()}

    tags: list[Tag] = []
    for n in normalized:
        t = existing.get(n)
        if t is None:
            t = Tag(name=n)
            session.add(t)
            tags.append(t)
        else:
            tags.append(t)

    await session.flush()
    return tags


async def list_tasks(
    session: AsyncSession,
    *,
    project_id: int,
    status: str | None = None,
    priority: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
) -> list[Task]:
    query = select(Task).options(selectinload(Task.tags)).where(Task.project_id == project_id)
    if not include_archived:
        query = query.where(Task.is_archived.is_(False))
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if q:
        query = query.where(Task.title.ilike(f"%{q}%"))
    if tag:
        query = query.join(Task.tags).where(Tag.name == tag.strip().lower())

    res = await session.execute(query.order_by(Task.id.desc()))
    return list(res.scalars().all())


async def get_task(session: AsyncSession, *, task_id: int, project_id: int) -> Task | None:
    res = await session.execute(
        select(Task)
        .options(selectinload(Task.tags))
        .where(Task.id == task_id)
        .where(Task.project_id == project_id)
    )
    return res.scalar_one_or_none()


async def update_task(
    session: AsyncSession,
    *,
    task: Task,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    is_archived: bool | None = None,
) -> Task:
    if status is not None:
        validate_transition(task.status, status)
        task.status = status

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if priority is not None:
        task.priority = priority

    if tags is not None:
        task.tags = await _get_or_create_tags(session, tags)

    if is_archived is not None:
        if is_archived and not task.is_archived:
            task.is_archived = True
            task.archived_at = datetime.now(timezone.utc)
        elif (not is_archived) and task.is_archived:
            task.is_archived = False
            task.archived_at = None

    await session.commit()
    await session.refresh(task)
    await session.refresh(task, attribute_names=["tags"])
    return task
