import pytest

from tests.helpers import attach_json, auth_headers, httpx_request_with_allure


def _create_project(urls, client, token: str, name: str = "Proj") -> dict:
    r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(token),
        json={"name": name},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_task(urls, client, token: str, project_id: int, title: str = "T1") -> dict:
    r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(token),
        json={"title": title, "description": "d", "priority": "medium", "tags": ["x"]},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.api
def test_tasks_projects_crud_and_task_flow(urls, client, user_token) -> None:
    project = _create_project(urls, client, user_token, name="Проект 1")
    attach_json("project", project)

    list_r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
    )
    assert list_r.status_code == 200, list_r.text
    assert any(p["id"] == project["id"] for p in list_r.json())

    get_r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project['id']}",
        headers=auth_headers(user_token),
    )
    assert get_r.status_code == 200, get_r.text

    task = _create_task(urls, client, user_token, project_id=project["id"], title="Задача 1")
    attach_json("task", task)
    assert task["status"] == "todo"

    patch_r = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['tasks']}/projects/{project['id']}/tasks/{task['id']}",
        headers=auth_headers(user_token),
        json={"status": "in_progress"},
    )
    assert patch_r.status_code == 200, patch_r.text
    assert patch_r.json()["status"] == "in_progress"

    done_r = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['tasks']}/projects/{project['id']}/tasks/{task['id']}",
        headers=auth_headers(user_token),
        json={"status": "done"},
    )
    assert done_r.status_code == 200, done_r.text
    assert done_r.json()["status"] == "done"

    archive_r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project['id']}/tasks/{task['id']}/archive",
        headers=auth_headers(user_token),
    )
    assert archive_r.status_code == 200, archive_r.text
    assert archive_r.json()["is_archived"] is True

    restore_r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project['id']}/tasks/{task['id']}/restore",
        headers=auth_headers(user_token),
    )
    assert restore_r.status_code == 200, restore_r.text
    assert restore_r.json()["is_archived"] is False


@pytest.mark.api
def test_tasks_requires_auth(urls, client) -> None:
    r = httpx_request_with_allure(client, "GET", f"{urls['tasks']}/projects")
    assert r.status_code in (401, 403), r.text


@pytest.mark.api
def test_tasks_invalid_transition_returns_400(urls, client, user_token) -> None:
    project = _create_project(urls, client, user_token, name="Проект 2")
    task = _create_task(urls, client, user_token, project_id=project["id"], title="Задача 2")

    # todo -> done is invalid
    r = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['tasks']}/projects/{project['id']}/tasks/{task['id']}",
        headers=auth_headers(user_token),
        json={"status": "done"},
    )
    assert r.status_code == 400, r.text
