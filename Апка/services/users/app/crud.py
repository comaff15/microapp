from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def create_user(session: AsyncSession, *, email: str, password_hash: str, role: str = "user") -> User:
    user = User(email=email, password_hash=password_hash, role=role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def list_users(session: AsyncSession, *, limit: int = 200, before_id: int | None = None) -> list[User]:
    q = select(User)
    if before_id is not None:
        q = q.where(User.id < before_id)
    q = q.order_by(User.id.desc()).limit(limit)
    res = await session.execute(q)
    return list(res.scalars().all())


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    res = await session.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()


async def update_user_admin(
    session: AsyncSession,
    *,
    user: User,
    role: str | None = None,
    is_active: bool | None = None,
) -> User:
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    await session.commit()
    await session.refresh(user)
    return user
