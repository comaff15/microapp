import pytest

from tests.helpers import auth_headers, httpx_request_with_allure


def _register_and_login(urls, client, email: str) -> str:
    r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert r.status_code == 201, r.text

    login = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.mark.api
def test_viewer_role_cannot_create_or_patch_tasks(urls, client, user_token, unique_email) -> None:
    # create project as owner
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "RO Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    viewer_email = unique_email
    viewer_token = _register_and_login(urls, client, viewer_email)

    # add viewer
    add = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/members",
        headers=auth_headers(user_token),
        json={"user_email": viewer_email, "role": "viewer"},
    )
    assert add.status_code == 201, add.text

    # viewer cannot create task
    create = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(viewer_token),
        json={"title": "x", "description": None, "priority": "medium", "tags": []},
    )
    assert create.status_code == 403, create.text

    # owner creates task
    t = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        json={"title": "owner-task", "description": None, "priority": "medium", "tags": []},
    )
    assert t.status_code == 201, t.text
    task_id = t.json()["id"]

    # viewer can list
    lst = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(viewer_token),
    )
    assert lst.status_code == 200, lst.text

    # viewer cannot patch
    patch = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['tasks']}/projects/{project_id}/tasks/{task_id}",
        headers=auth_headers(viewer_token),
        json={"title": "hacked"},
    )
    assert patch.status_code == 403, patch.text
