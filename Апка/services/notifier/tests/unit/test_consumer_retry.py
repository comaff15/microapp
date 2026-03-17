from __future__ import annotations

from typing import Any

import pytest

import app.consumer as consumer_mod


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
@pytest.mark.asyncio
async def test_notifier_consumer_on_success_logs_sent_no_retry(monkeypatch) -> None:
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
        logs.append(
            {
                "routing_key": routing_key,
                "payload_json": payload_json,
                "attempt": attempt,
                "status": status,
                "is_dead_letter": is_dead_letter,
                "error": error,
            }
        )

    monkeypatch.setattr(consumer_mod, "create_log", _fake_create_log)
    monkeypatch.setattr(consumer_mod, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(consumer_mod.random, "random", lambda: 0.9)  # no fail

    msg = _DummyMessage(routing_key="task.created", body=b"{}", headers={"x-attempt": 2})
    c = consumer_mod.NotifierConsumer()
    c._queue = _DummyQueue([msg])
    c._channel = _DummyChannel()

    await c.run()

    assert [l["status"] for l in logs] == ["sent"]
    assert c._channel.default_exchange.published == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_notifier_consumer_on_fail_retries_with_incremented_attempt(monkeypatch) -> None:
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
    monkeypatch.setattr(consumer_mod.random, "random", lambda: 0.0)  # fail

    # keep max_attempts high
    monkeypatch.setattr(consumer_mod.settings, "max_attempts", 5)

    msg = _DummyMessage(routing_key="task.updated", body=b"{}", headers={"x-attempt": 1})
    c = consumer_mod.NotifierConsumer()
    c._queue = _DummyQueue([msg])
    c._channel = _DummyChannel()

    await c.run()

    assert logs[0]["status"] == "failed"
    assert c._channel.default_exchange.published
    published = c._channel.default_exchange.published[0]
    assert published["routing_key"] == consumer_mod.settings.queue_name

    # aio_pika.Message carries headers we set; just validate they include increment
    published_headers = getattr(published["message"], "headers", None)
    assert published_headers is not None
    assert published_headers["x-attempt"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_notifier_consumer_on_fail_at_max_attempts_writes_dead_letter_and_no_retry(monkeypatch) -> None:
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
    monkeypatch.setattr(consumer_mod.random, "random", lambda: 0.0)  # fail

    monkeypatch.setattr(consumer_mod.settings, "max_attempts", 2)

    msg = _DummyMessage(routing_key="task.deleted", body=b"{}", headers={"x-attempt": 2})
    c = consumer_mod.NotifierConsumer()
    c._queue = _DummyQueue([msg])
    c._channel = _DummyChannel()

    await c.run()

    # first log is failed, then dead
    assert [l["status"] for l in logs] == ["failed", "dead"]
    assert logs[1]["is_dead_letter"] is True
    assert c._channel.default_exchange.published == []
