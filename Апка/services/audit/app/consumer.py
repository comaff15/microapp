import asyncio
import json

import aio_pika

from app.core.config import settings
from app.crud import create_event
from app.db import SessionLocal


class AuditConsumer:
    def __init__(self) -> None:
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._queue: aio_pika.Queue | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.amqp_url)
        self._channel = await self._connection.channel()

        exchange = await self._channel.declare_exchange(settings.events_exchange, aio_pika.ExchangeType.TOPIC)
        self._queue = await self._channel.declare_queue("audit.events", durable=True)

        await self._queue.bind(exchange, routing_key="#")

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def run(self) -> None:
        if self._queue is None:
            return

        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    routing_key = message.routing_key or ""
                    body = message.body.decode("utf-8")
                    try:
                        parsed = json.loads(body)
                        payload_json = json.dumps(parsed, ensure_ascii=False)
                    except Exception:
                        payload_json = json.dumps({"raw": body}, ensure_ascii=False)

                    async with SessionLocal() as session:
                        await create_event(session, routing_key=routing_key, payload_json=payload_json)


consumer = AuditConsumer()


async def wait_for_broker_ready() -> None:
    while True:
        try:
            connection = await aio_pika.connect_robust(settings.amqp_url)
            await connection.close()
            return
        except Exception:
            await asyncio.sleep(1)
