import pytest

from tests.helpers import attach_json, auth_headers, httpx_request_with_allure


@pytest.mark.api
def test_users_register_and_login_and_me(urls, client, unique_email) -> None:
    register_r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    assert register_r.status_code == 201, register_r.text
    user = register_r.json()
    attach_json("registered_user", user)

    login_r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/login",
        json={"email": unique_email, "password": "password123"},
    )
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]
    assert isinstance(token, str) and token

    me_r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['users']}/users/me",
        headers=auth_headers(token),
    )
    assert me_r.status_code == 200, me_r.text
    me = me_r.json()
    assert me["email"] == unique_email


@pytest.mark.api
def test_users_register_duplicate_email_returns_409(urls, client, unique_email) -> None:
    r1 = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    assert r1.status_code == 201, r1.text

    r2 = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    assert r2.status_code == 409, r2.text


@pytest.mark.api
def test_users_login_wrong_password_returns_401(urls, client, unique_email) -> None:
    reg = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    assert reg.status_code == 201, reg.text

    login = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/login",
        json={"email": unique_email, "password": "wrong-password"},
    )
    assert login.status_code == 401, login.text


@pytest.mark.api
def test_users_me_requires_auth(urls, client) -> None:
    r = httpx_request_with_allure(client, "GET", f"{urls['users']}/users/me")
    assert r.status_code in (401, 403), r.text
