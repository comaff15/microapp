from datetime import datetime

from pydantic import BaseModel


class NotificationPublic(BaseModel):
    id: int
    routing_key: str
    payload_json: str
    attempt: int
    status: str
    is_dead_letter: bool
    error: str | None
    created_at: datetime
