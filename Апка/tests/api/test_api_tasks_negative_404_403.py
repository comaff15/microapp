import pytest

from tests.helpers import auth_headers, httpx_request_with_allure


@pytest.mark.api
def test_get_missing_project_returns_403_or_404(urls, client, user_token) -> None:
    # service checks membership first; depending on implementation it can be 403 or 404
    r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/999999",
        headers=auth_headers(user_token),
    )
    assert r.status_code in (403, 404), r.text


@pytest.mark.api
def test_get_missing_task_returns_404(urls, client, user_token) -> None:
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Neg Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks/999999",
        headers=auth_headers(user_token),
    )
    assert r.status_code == 404, r.text


@pytest.mark.api
def test_member_invalid_role_returns_400(urls, client, user_token) -> None:
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Role Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    add = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/members",
        headers=auth_headers(user_token),
        json={"user_email": "x@example.com", "role": "bad"},
    )
    assert add.status_code == 400, add.text


@pytest.mark.api
def test_member_setting_owner_role_directly_returns_409(urls, client, user_token) -> None:
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Owner Role Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    add = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/members",
        headers=auth_headers(user_token),
        json={"user_email": "x@example.com", "role": "owner"},
    )
    assert add.status_code == 409, add.text
