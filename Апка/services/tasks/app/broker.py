import json
from datetime import datetime, timezone

import aio_pika

from app.core.config import settings


class EventPublisher:
    def __init__(self) -> None:
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.amqp_url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(settings.events_exchange, aio_pika.ExchangeType.TOPIC)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def publish(self, routing_key: str, payload: dict) -> None:
        if self._exchange is None:
            return

        body = json.dumps(
            {
                "routing_key": routing_key,
                "payload": payload,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        ).encode("utf-8")

        await self._exchange.publish(aio_pika.Message(body=body, content_type="application/json"), routing_key=routing_key)


publisher = EventPublisher()
