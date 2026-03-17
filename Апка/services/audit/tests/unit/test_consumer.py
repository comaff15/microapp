import json
from typing import Any

import pytest

import app.consumer as consumer_mod


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyMessage:
    def __init__(self, *, routing_key: str | None, body: bytes):
        self.routing_key = routing_key
        self.body = body

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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_audit_consumer_parses_json_payload_and_passes_compacted_json(monkeypatch) -> None:
    calls: list[dict] = []

    async def _fake_create_event(session, *, routing_key: str, payload_json: str):
        calls.append({"routing_key": routing_key, "payload_json": payload_json})

    monkeypatch.setattr(consumer_mod, "create_event", _fake_create_event)
    monkeypatch.setattr(consumer_mod, "SessionLocal", lambda: _DummySession())

    msg = _DummyMessage(routing_key="task.created", body=json.dumps({"a": 1, "b": "тест"}).encode("utf-8"))
    c = consumer_mod.AuditConsumer()
    c._queue = _DummyQueue([msg])

    await c.run()

    assert len(calls) == 1
    assert calls[0]["routing_key"] == "task.created"
    assert json.loads(calls[0]["payload_json"]) == {"a": 1, "b": "тест"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_audit_consumer_wraps_non_json_payload_as_raw(monkeypatch) -> None:
    calls: list[dict] = []

    async def _fake_create_event(session, *, routing_key: str, payload_json: str):
        calls.append({"routing_key": routing_key, "payload_json": payload_json})

    monkeypatch.setattr(consumer_mod, "create_event", _fake_create_event)
    monkeypatch.setattr(consumer_mod, "SessionLocal", lambda: _DummySession())

    msg = _DummyMessage(routing_key=None, body=b"not-json")
    c = consumer_mod.AuditConsumer()
    c._queue = _DummyQueue([msg])

    await c.run()

    assert len(calls) == 1
    assert calls[0]["routing_key"] == ""
    assert json.loads(calls[0]["payload_json"]) == {"raw": "not-json"}
