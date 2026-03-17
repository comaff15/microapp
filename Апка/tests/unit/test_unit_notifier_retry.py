import os
import threading
import asyncio
from typing import Any

import pytest

from tests.unit.service_import import activate_service_app


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyMessage:
    def __init__(
        self,
        *,
        routing_key: str | None,
        body: bytes,
        headers: dict[str, Any] | None = None,
        content_type: str | None = "application/json",
    ):
        self.routing_key = routing_key
        self.body = body
        self.headers = headers
        self.content_type = content_type

    class _Process:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def process(self, *args: Any, **kwargs: Any):
        return self._Process()


class _QueueIterator:
    def __init__(self, messages):
        self._messages = list(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


class _DummyQueue:
    def __init__(self, messages):
        self._messages = messages

    def iterator(self):
        return _QueueIterator(self._messages)


class _DummyExchange:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(self, message, *, routing_key: str):
        self.published.append({"message": message, "routing_key": routing_key})


class _DummyChannel:
    def __init__(self) -> None:
        self.default_exchange = _DummyExchange()


@pytest.mark.unit
def test_notifier_consumer_retries_and_dead_letters(monkeypatch) -> None:
    activate_service_app(os.path.join(os.path.dirname(__file__), "..", "..", "services", "notifier"))

    import app.consumer as consumer_mod

    logs: list[dict[str, Any]] = []

    async def _fake_create_log(
        session,
        *,
        routing_key: str,
        payload_json: str,
        attempt: int,
        status: str,
        is_dead_letter: bool,
        error: str | None,
    ):
        logs.append({"status": status, "attempt": attempt, "is_dead_letter": is_dead_letter})

    monkeypatch.setattr(consumer_mod, "create_log", _fake_create_log)
    monkeypatch.setattr(consumer_mod, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(consumer_mod.random, "random", lambda: 0.0)
    monkeypatch.setattr(consumer_mod.settings, "max_attempts", 2)

    msg = _DummyMessage(routing_key="task.created", body=b"{}", headers={"x-attempt": 2})

    c = consumer_mod.NotifierConsumer()
    c._queue = _DummyQueue([msg])
    c._channel = _DummyChannel()

    def _run() -> None:
        asyncio.run(c.run())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=5.0)
    assert not t.is_alive(), "consumer did not finish"

    assert [x["status"] for x in logs] == ["failed", "dead"]
    assert c._channel.default_exchange.published == []
