import pytest

from tests.helpers import attach_json, auth_headers, eventually, httpx_request_with_allure


@pytest.mark.integration
def test_notifier_retries_or_dead_letters_under_flaky_provider(urls, client, user_token) -> None:
    # Create project
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Resilience Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    # Generate enough events to very likely hit simulated failures (20% probability)
    for i in range(25):
        t = httpx_request_with_allure(
            client,
            "POST",
            f"{urls['tasks']}/projects/{project_id}/tasks",
            headers=auth_headers(user_token),
            json={"title": f"R{i}", "description": None, "priority": "medium", "tags": []},
        )
        assert t.status_code == 201, t.text

    def _assert_has_retry_or_dlq():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['notifier']}/notifications",
            params={"limit": 500},
        )
        assert r.status_code == 200, r.text
        items = r.json()
        attach_json("notifier_logs", items)

        # We expect at least some task.created logs.
        created = [x for x in items if x.get("routing_key") == "task.created"]
        assert created, "No task.created logs yet"

        # Retry evidence: attempt > 1 OR failed/dead status entries.
        has_retry = any(int(x.get("attempt") or 1) > 1 for x in created)
        has_fail_or_dead = any(x.get("status") in ("failed", "dead") for x in created)

        assert has_retry or has_fail_or_dead, "No retry/dead-letter evidence yet"

    eventually(_assert_has_retry_or_dlq, timeout_s=60.0, interval_s=2.0)
