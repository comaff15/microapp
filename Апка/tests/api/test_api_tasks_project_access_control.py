import pytest

from tests.helpers import auth_headers, httpx_request_with_allure


@pytest.mark.api
def test_project_not_member_returns_403(urls, client, user_token, unique_email) -> None:
    # create project with user_token
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "ACL Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    # register second user
    r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    assert r.status_code == 201, r.text

    login = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/login",
        json={"email": unique_email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    token2 = login.json()["access_token"]

    # not a member -> 403
    get_r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}",
        headers=auth_headers(token2),
    )
    assert get_r.status_code == 403, get_r.text
