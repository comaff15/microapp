import pytest

from tests.helpers import attach_json, httpx_request_with_allure


@pytest.mark.contract
def test_openapi_available_for_all_services(urls, client) -> None:
    for name in ("users", "tasks", "audit", "notifier", "gateway"):
        base = urls[name]
        r = httpx_request_with_allure(client, "GET", f"{base}/openapi.json")
        assert r.status_code == 200, f"{name}: {r.status_code} {r.text}"
        data = r.json()
        attach_json(f"{name}.openapi", data)
        assert isinstance(data.get("openapi"), str)
        assert isinstance(data.get("paths"), dict) and data["paths"]
