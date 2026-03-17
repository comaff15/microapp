import pytest

from tests.helpers import attach_json, auth_headers, httpx_request_with_allure


@pytest.mark.api
def test_admin_can_patch_user_role_and_deactivate(urls, client, admin_token, unique_email) -> None:
    # create a normal user
    reg = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    assert reg.status_code == 201, reg.text
    user = reg.json()
    user_id = user["id"]

    # make them admin
    patch1 = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['users']}/admin/users/{user_id}",
        headers=auth_headers(admin_token),
        json={"role": "admin"},
    )
    assert patch1.status_code == 200, patch1.text
    attach_json("patched_role", patch1.json())
    assert patch1.json()["role"] == "admin"

    # deactivate
    patch2 = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['users']}/admin/users/{user_id}",
        headers=auth_headers(admin_token),
        json={"is_active": False},
    )
    assert patch2.status_code == 200, patch2.text
    assert patch2.json()["is_active"] is False

    # login must fail for inactive user
    login = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/login",
        json={"email": unique_email, "password": "password123"},
    )
    assert login.status_code == 403, login.text


@pytest.mark.api
def test_patch_user_requires_admin(urls, client, user_token) -> None:
    r = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['users']}/admin/users/1",
        headers=auth_headers(user_token),
        json={"role": "admin"},
    )
    assert r.status_code in (401, 403), r.text
