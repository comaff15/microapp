import pytest

from tests.helpers import attach_json, auth_headers, eventually, httpx_request_with_allure


@pytest.mark.api
def test_audit_filter_and_before_id_pagination(urls, client, user_token) -> None:
    # generate at least a couple events
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Audit Page Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    for i in range(3):
        t = httpx_request_with_allure(
            client,
            "POST",
            f"{urls['tasks']}/projects/{project_id}/tasks",
            headers=auth_headers(user_token),
            json={"title": f"T{i}", "description": None, "priority": "medium", "tags": []},
        )
        assert t.status_code == 201, t.text

    def _fetch_first_page():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['audit']}/events",
            params={"limit": 2, "routing_key": "task.created"},
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        return items

    items = eventually(_fetch_first_page, timeout_s=25.0, interval_s=1.0)
    attach_json("audit_page1", items)

    before_id = items[-1]["id"]

    page2 = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['audit']}/events",
        params={"limit": 2, "routing_key": "task.created", "before_id": before_id},
    )
    assert page2.status_code == 200, page2.text
    attach_json("audit_page2", page2.json())

    # ids must be strictly lower than before_id
    assert all(e["id"] < before_id for e in page2.json())
