from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.deps import get_db
from app.schemas import NotificationPublic

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationPublic])
async def list_notifications(
    limit: int = 200,
    status: str | None = None,
    before_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    logs = await crud.list_logs(db, limit=limit, status=status, before_id=before_id)
    return [
        NotificationPublic(
            id=l.id,
            routing_key=l.routing_key,
            payload_json=l.payload_json,
            attempt=l.attempt,
            status=l.status,
            is_dead_letter=l.is_dead_letter,
            error=l.error,
            created_at=l.created_at,
        )
        for l in logs
    ]
