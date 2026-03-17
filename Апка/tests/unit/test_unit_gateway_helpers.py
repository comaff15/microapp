import os
import sys
import threading
import asyncio

import pytest


def _activate_gateway_main() -> None:
    gateway_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "services", "gateway", "app"))
    if gateway_app_dir not in sys.path:
        sys.path.insert(0, gateway_app_dir)


class _DummyRequest:
    def __init__(self, cookies: dict[str, str] | None = None):
        self.cookies = cookies or {}


@pytest.mark.unit
def test_gateway_auth_headers_and_redirect() -> None:
    _activate_gateway_main()

    import main as gateway_main

    assert gateway_main._auth_headers(_DummyRequest({})) == {}
    assert gateway_main._auth_headers(_DummyRequest({"access_token": "t"})) == {"Authorization": "Bearer t"}

    resp = gateway_main._redirect("/login")
    assert resp.status_code == 303


@pytest.mark.unit
def test_gateway_require_admin_variants(monkeypatch) -> None:
    _activate_gateway_main()

    import main as gateway_main

    def _run(coro):
        out: dict[str, object] = {}

        def _t():
            out["result"] = asyncio.run(coro)

        th = threading.Thread(target=_t, daemon=True)
        th.start()
        th.join(timeout=5.0)
        assert not th.is_alive(), "coroutine did not finish"
        return out.get("result")

    async def _none(_):
        return None

    monkeypatch.setattr(gateway_main, "_get_current_user", _none)
    assert _run(gateway_main._require_admin(_DummyRequest())) is None

    async def _user(_):
        return {"id": 1, "role": "user"}

    monkeypatch.setattr(gateway_main, "_get_current_user", _user)
    r = _run(gateway_main._require_admin(_DummyRequest()))
    assert r["__forbidden__"] is True

    async def _admin(_):
        return {"id": 1, "role": "admin"}

    monkeypatch.setattr(gateway_main, "_get_current_user", _admin)
    r2 = _run(gateway_main._require_admin(_DummyRequest()))
    assert r2["role"] == "admin"
    assert "__forbidden__" not in r2
