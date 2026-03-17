import json

import jsonschema
import pytest

from tests.helpers import attach_json, auth_headers, eventually, httpx_request_with_allure


_TASK_EVENT_SCHEMA = {
    "type": "object",
    "required": ["task_id", "project_id", "owner_email", "title", "status", "priority", "tags"],
    "properties": {
        "task_id": {"type": "integer"},
        "project_id": {"type": "integer"},
        "owner_email": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "string"},
        "priority": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "is_archived": {"type": "boolean"},
        "ts": {"type": "string"},
    },
    "additionalProperties": True,
}


@pytest.mark.contract
def test_audit_task_created_payload_conforms_to_schema(urls, client, user_token) -> None:
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Contract Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    t = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        json={"title": "Contract Task", "description": None, "priority": "medium", "tags": ["c"]},
    )
    assert t.status_code == 201, t.text
    task_id = t.json()["id"]

    def _get_event():
        r = httpx_request_with_allure(
            client,
            "GET",
            f"{urls['audit']}/events",
            params={"limit": 200, "routing_key": "task.created"},
        )
        assert r.status_code == 200
        for e in r.json():
            if e.get("routing_key") == "task.created" and str(task_id) in (e.get("payload_json") or ""):
                return e
        assert False, "event not found"

    ev = eventually(_get_event, timeout_s=25.0, interval_s=1.0)
    attach_json("audit_event", ev)

    body = json.loads(ev["payload_json"])
    assert body.get("routing_key") == "task.created"
    assert "payload" in body
    assert "ts" in body
    jsonschema.validate(body["payload"], _TASK_EVENT_SCHEMA)
