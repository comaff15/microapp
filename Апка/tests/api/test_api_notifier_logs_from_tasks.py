import pytest

from tests.helpers import attach_json, auth_headers, eventually, httpx_request_with_allure


@pytest.mark.api
def test_notifier_logs_task_events(urls, client, user_token) -> None:
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Notif Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    t = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        json={"title": "Notif Task", "description": None, "priority": "medium", "tags": []},
    )
    assert t.status_code == 201, t.text

    def _assert_log_present():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['notifier']}/notifications",
            params={"limit": 100},
        )
        assert r.status_code == 200, r.text
        items = r.json()
        attach_json("notifier_logs", items)

        # notifier can be flaky; accept sent/failed/dead as long as event is recorded
        assert any((x.get("routing_key") == "task.created") for x in items)

    eventually(_assert_log_present, timeout_s=25.0, interval_s=1.0)
