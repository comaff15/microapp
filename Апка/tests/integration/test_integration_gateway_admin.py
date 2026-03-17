import pytest

from tests.helpers import httpx_request_with_allure


@pytest.mark.integration
def test_gateway_admin_status_requires_login(urls, client) -> None:
    r = httpx_request_with_allure(client, "GET", f"{urls['gateway']}/admin/status", follow_redirects=False)
    assert r.status_code in (302, 303), r.text


@pytest.mark.integration
def test_gateway_admin_status_forbidden_for_non_admin(urls, client, user_token) -> None:
    client.cookies.set("access_token", user_token)

    r = httpx_request_with_allure(client, "GET", f"{urls['gateway']}/admin/status")
    assert r.status_code == 200, r.text

    # Forbidden template is rendered
    assert "требуемая роль" in r.text.lower()


@pytest.mark.integration
def test_gateway_admin_status_ok_for_admin(urls, client, admin_token) -> None:
    client.cookies.set("access_token", admin_token)

    r = httpx_request_with_allure(client, "GET", f"{urls['gateway']}/admin/status")
    assert r.status_code == 200, r.text

    # Should contain service names and HTTP statuses
    body = r.text.lower()
    assert "users" in body
    assert "tasks" in body
    assert "audit" in body
    assert "notifier" in body
    assert "http" in body
