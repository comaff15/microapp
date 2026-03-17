from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def create_event(session: AsyncSession, *, routing_key: str, payload_json: str) -> AuditEvent:
    ev = AuditEvent(routing_key=routing_key, payload_json=payload_json)
    session.add(ev)
    await session.commit()
    await session.refresh(ev)
    return ev


async def list_events(
    session: AsyncSession,
    *,
    limit: int = 200,
    routing_key: str | None = None,
    before_id: int | None = None,
) -> list[AuditEvent]:
    q = select(AuditEvent)

    if routing_key:
        q = q.where(AuditEvent.routing_key == routing_key)
    if before_id is not None:
        q = q.where(AuditEvent.id < before_id)

    q = q.order_by(AuditEvent.id.desc()).limit(limit)

    res = await session.execute(q)
    return list(res.scalars().all())
