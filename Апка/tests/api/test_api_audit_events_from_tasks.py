import json

import pytest

from tests.helpers import attach_json, auth_headers, eventually, httpx_request_with_allure


@pytest.mark.api
def test_audit_receives_task_created_event(urls, client, user_token) -> None:
    # create project
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Audit Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    # create task -> should emit task.created
    t = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        json={"title": "Audit Task", "description": None, "priority": "medium", "tags": []},
    )
    assert t.status_code == 201, t.text
    task_id = t.json()["id"]

    def _assert_event_present():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['audit']}/events",
            params={"limit": 50, "routing_key": "task.created"},
        )
        assert r.status_code == 200, r.text
        items = r.json()
        attach_json("audit_events", items)
        assert any(
            (e.get("routing_key") == "task.created")
            and (str(task_id) in (e.get("payload_json") or ""))
            for e in items
        )

        # ensure payload_json is valid json string
        for e in items:
            if e.get("routing_key") == "task.created":
                json.loads(e["payload_json"])

    eventually(_assert_event_present, timeout_s=20.0, interval_s=1.0)
