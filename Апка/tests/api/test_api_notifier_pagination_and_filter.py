import pytest

from tests.helpers import attach_json, auth_headers, eventually, httpx_request_with_allure


@pytest.mark.api
def test_notifier_filter_and_before_id_pagination(urls, client, user_token) -> None:
    # generate at least a couple events (notifier will log them)
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Notif Page Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    for i in range(3):
        t = httpx_request_with_allure(
            client,
            "POST",
            f"{urls['tasks']}/projects/{project_id}/tasks",
            headers=auth_headers(user_token),
            json={"title": f"N{i}", "description": None, "priority": "medium", "tags": []},
        )
        assert t.status_code == 201, t.text

    def _fetch_page():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['notifier']}/notifications",
            params={"limit": 3},
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        return items

    items = eventually(_fetch_page, timeout_s=30.0, interval_s=1.0)
    attach_json("notifier_page1", items)

    before_id = items[-1]["id"]

    page2 = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['notifier']}/notifications",
        params={"limit": 3, "before_id": before_id},
    )
    assert page2.status_code == 200, page2.text
    attach_json("notifier_page2", page2.json())

    assert all(x["id"] < before_id for x in page2.json())


@pytest.mark.api
def test_notifier_status_filter_accepts_sent_failed_dead(urls, client) -> None:
    # should not crash, must return list
    for status in ("sent", "failed", "dead"):
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['notifier']}/notifications",
            params={"limit": 10, "status": status},
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)
