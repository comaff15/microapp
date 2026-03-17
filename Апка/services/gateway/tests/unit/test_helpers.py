import pytest

import main as gateway_main


class _DummyRequest:
    def __init__(self, cookies: dict[str, str] | None = None):
        self.cookies = cookies or {}


@pytest.mark.unit
def test_auth_headers_empty_when_no_cookie() -> None:
    req = _DummyRequest(cookies={})
    assert gateway_main._auth_headers(req) == {}


@pytest.mark.unit
def test_auth_headers_has_bearer_when_cookie_present() -> None:
    req = _DummyRequest(cookies={"access_token": "t"})
    assert gateway_main._auth_headers(req) == {"Authorization": "Bearer t"}


@pytest.mark.unit
def test_redirect_uses_303() -> None:
    resp = gateway_main._redirect("/login")
    assert resp.status_code == 303


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_admin_returns_none_when_no_user(monkeypatch) -> None:
    async def _fake_get_current_user(request):
        return None

    monkeypatch.setattr(gateway_main, "_get_current_user", _fake_get_current_user)
    assert await gateway_main._require_admin(_DummyRequest()) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_admin_marks_forbidden_when_not_admin(monkeypatch) -> None:
    async def _fake_get_current_user(request):
        return {"id": 1, "role": "user"}

    monkeypatch.setattr(gateway_main, "_get_current_user", _fake_get_current_user)
    r = await gateway_main._require_admin(_DummyRequest())
    assert r["__forbidden__"] is True
    assert r["role"] == "user"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_admin_returns_user_when_admin(monkeypatch) -> None:
    async def _fake_get_current_user(request):
        return {"id": 1, "role": "admin"}

    monkeypatch.setattr(gateway_main, "_get_current_user", _fake_get_current_user)
    r = await gateway_main._require_admin(_DummyRequest())
    assert r["role"] == "admin"
    assert "__forbidden__" not in r
