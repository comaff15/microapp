from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.deps import get_db
from app.schemas import AuditEventPublic

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[AuditEventPublic])
async def list_events(
    limit: int = 200,
    routing_key: str | None = None,
    before_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    events = await crud.list_events(db, limit=limit, routing_key=routing_key, before_id=before_id)
    return [
        AuditEventPublic(id=e.id, routing_key=e.routing_key, payload_json=e.payload_json, received_at=e.received_at)
        for e in events
    ]
