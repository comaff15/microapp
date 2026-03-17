import pytest

from tests.helpers import attach_json, auth_headers, httpx_request_with_allure


def _create_project(urls, client, token: str, name: str) -> int:
    r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(token),
        json={"name": name},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_task(urls, client, token: str, project_id: int, *, title: str, tags: list[str]):
    r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(token),
        json={"title": title, "description": None, "priority": "medium", "tags": tags},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.api
def test_list_tasks_filters_by_q_tag_status_and_include_archived(urls, client, user_token) -> None:
    project_id = _create_project(urls, client, user_token, name="Filters Proj")

    t1 = _create_task(urls, client, user_token, project_id, title="Alpha task", tags=["red"])
    t2 = _create_task(urls, client, user_token, project_id, title="Beta task", tags=["blue"])

    # move t2 to in_progress
    p = httpx_request_with_allure(
        client,
        "PATCH",
        f"{urls['tasks']}/projects/{project_id}/tasks/{t2['id']}",
        headers=auth_headers(user_token),
        json={"status": "in_progress"},
    )
    assert p.status_code == 200

    # q filter
    q_r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        params={"q": "Alpha"},
    )
    assert q_r.status_code == 200
    attach_json("tasks_q", q_r.json())
    assert any(x["id"] == t1["id"] for x in q_r.json())
    assert all("alpha" in x["title"].lower() for x in q_r.json())

    # tag filter
    tag_r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        params={"tag": "blue"},
    )
    assert tag_r.status_code == 200
    attach_json("tasks_tag", tag_r.json())
    assert any(x["id"] == t2["id"] for x in tag_r.json())
    assert all("blue" in x.get("tags", []) for x in tag_r.json())

    # status filter
    st_r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        params={"status_filter": "in_progress"},
    )
    assert st_r.status_code == 200
    attach_json("tasks_status", st_r.json())
    assert all(x["status"] == "in_progress" for x in st_r.json())

    # archive t1 and ensure it is excluded by default
    ar = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks/{t1['id']}/archive",
        headers=auth_headers(user_token),
    )
    assert ar.status_code == 200

    default_list = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
    )
    assert default_list.status_code == 200
    assert all(x["is_archived"] is False for x in default_list.json())

    with_archived = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        params={"include_archived": True},
    )
    assert with_archived.status_code == 200
    attach_json("tasks_include_archived", with_archived.json())
    assert any(x["id"] == t1["id"] for x in with_archived.json())
