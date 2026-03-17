import re

import pytest

from tests.helpers import attach_text, eventually, httpx_request_with_allure


def _extract_first_int(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    assert m is not None, f"Pattern not found: {pattern}"
    return int(m.group(1))


@pytest.mark.integration
def test_gateway_full_flow_creates_events(urls, client, unique_email) -> None:
    gateway = urls["gateway"]

    # Register via Gateway (form)
    reg = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/register",
        data={"email": unique_email, "password": "password123"},
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert reg.status_code in (302, 303), reg.text

    # Login via Gateway -> should set access_token cookie
    login = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/login",
        data={"email": unique_email, "password": "password123"},
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert login.status_code in (302, 303), login.text

    # Cookie jar must contain access_token
    assert client.cookies.get("access_token")

    # Create project via Gateway (HTMX table response)
    proj = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/projects",
        data={"name": "Интеграционный проект"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert proj.status_code == 200, proj.text

    # Extract project id from links: /projects/{id}
    project_id = _extract_first_int(r"/projects/(\d+)\"", proj.text)

    # Create task via Gateway
    tasks_table = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/projects/{project_id}/tasks",
        data={"title": "Интеграционная задача", "description": "", "priority": "medium", "tags": "x"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert tasks_table.status_code == 200, tasks_table.text

    # Extract task id from row ids: task-row-{id}
    task_id = _extract_first_int(r"task-row-(\d+)\"", tasks_table.text)

    # Archive
    archived = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/projects/{project_id}/tasks/{task_id}/archive",
        headers={"hx-request": "true"},
    )
    assert archived.status_code == 200, archived.text

    # Restore
    restored = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/projects/{project_id}/tasks/{task_id}/restore",
        headers={"hx-request": "true"},
    )
    assert restored.status_code == 200, restored.text

    attach_text("ids", f"project_id={project_id}, task_id={task_id}")

    # Eventually: audit has at least one task.* event containing task_id
    def _assert_audit():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['audit']}/events",
            params={"limit": 200},
        )
        assert r.status_code == 200
        assert any(str(task_id) in (e.get("payload_json") or "") for e in r.json())

    eventually(_assert_audit, timeout_s=25.0, interval_s=1.0)

    # Eventually: notifier has logs containing task_id
    def _assert_notifier():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['notifier']}/notifications",
            params={"limit": 200},
        )
        assert r.status_code == 200
        assert any(str(task_id) in (x.get("payload_json") or "") for x in r.json())

    eventually(_assert_notifier, timeout_s=35.0, interval_s=1.0)
