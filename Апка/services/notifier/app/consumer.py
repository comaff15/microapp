import asyncio
import json
import random

import aio_pika

from app.core.config import settings
from app.crud import create_log
from app.db import SessionLocal


class NotifierConsumer:
    def __init__(self) -> None:
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._queue: aio_pika.Queue | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.amqp_url)
        self._channel = await self._connection.channel()

        exchange = await self._channel.declare_exchange(settings.events_exchange, aio_pika.ExchangeType.TOPIC)
        self._queue = await self._channel.declare_queue(settings.queue_name, durable=True)

        await self._queue.bind(exchange, routing_key="task.*")

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def run(self) -> None:
        if self._queue is None:
            return

        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(requeue=False):
                    attempt = int(message.headers.get("x-attempt", 1)) if message.headers else 1
                    routing_key = message.routing_key or ""
                    body = message.body.decode("utf-8")

                    # Simulate flaky external provider.
                    fail = random.random() < 0.2
                    status = "sent"
                    err: str | None = None

                    if fail:
                        status = "failed"
                        err = "Simulated provider error"

                    async with SessionLocal() as session:
                        await create_log(
                            session,
                            routing_key=routing_key,
                            payload_json=body,
                            attempt=attempt,
                            status=status,
                            is_dead_letter=False,
                            error=err,
                        )

                    if fail:
                        if attempt >= settings.max_attempts:
                            async with SessionLocal() as session:
                                await create_log(
                                    session,
                                    routing_key=routing_key,
                                    payload_json=body,
                                    attempt=attempt,
                                    status="dead",
                                    is_dead_letter=True,
                                    error=err,
                                )
                            continue

                        # Retry by republishing with incremented attempt.
                        if self._channel is None:
                            continue

                        headers = dict(message.headers or {})
                        headers["x-attempt"] = attempt + 1

                        await self._channel.default_exchange.publish(
                            aio_pika.Message(
                                body=message.body,
                                headers=headers,
                                content_type=message.content_type,
                            ),
                            routing_key=settings.queue_name,
                        )


consumer = NotifierConsumer()


async def wait_for_broker_ready() -> None:
    while True:
        try:
            connection = await aio_pika.connect_robust(settings.amqp_url)
            await connection.close()
            return
        except Exception:
            await asyncio.sleep(1)
