import pytest

from tests.helpers import auth_headers, httpx_request_with_allure


@pytest.mark.api
def test_admin_list_users_requires_admin(urls, client, user_token) -> None:
    r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['users']}/admin/users",
        headers=auth_headers(user_token),
    )
    assert r.status_code in (401, 403), r.text


@pytest.mark.api
def test_admin_list_users_ok_for_admin(urls, client, admin_token) -> None:
    r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['users']}/admin/users",
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
