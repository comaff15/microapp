from datetime import datetime

from pydantic import BaseModel


class AuditEventPublic(BaseModel):
    id: int
    routing_key: str
    payload_json: str
    received_at: datetime
