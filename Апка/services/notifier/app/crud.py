from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationLog


async def create_log(
    session: AsyncSession,
    *,
    routing_key: str,
    payload_json: str,
    attempt: int,
    status: str,
    is_dead_letter: bool,
    error: str | None,
) -> NotificationLog:
    log = NotificationLog(
        routing_key=routing_key,
        payload_json=payload_json,
        attempt=attempt,
        status=status,
        is_dead_letter=is_dead_letter,
        error=error,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def list_logs(
    session: AsyncSession,
    *,
    limit: int = 200,
    status: str | None = None,
    before_id: int | None = None,
) -> list[NotificationLog]:
    q = select(NotificationLog)
    if status:
        q = q.where(NotificationLog.status == status)
    if before_id is not None:
        q = q.where(NotificationLog.id < before_id)
    q = q.order_by(NotificationLog.id.desc()).limit(limit)

    res = await session.execute(q)
    return list(res.scalars().all())
