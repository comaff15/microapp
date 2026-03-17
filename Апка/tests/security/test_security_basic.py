import pytest

from tests.helpers import attach_text, auth_headers, httpx_request_with_allure


@pytest.mark.security
def test_users_me_rejects_tampered_jwt(urls, client) -> None:
    token = "abc.def.ghi"  # invalid JWT
    r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['users']}/users/me",
        headers=auth_headers(token),
    )
    assert r.status_code == 401, r.text


@pytest.mark.security
def test_gateway_rejects_invalid_cookie_token_and_redirects_to_login(urls, client) -> None:
    client.cookies.set("access_token", "abc.def.ghi")
    r = httpx_request_with_allure(client, "GET", f"{urls['gateway']}/projects", follow_redirects=False)
    assert r.status_code in (302, 303), r.text


@pytest.mark.security
def test_tasks_search_sql_injection_like_query_does_not_500(urls, client, user_token) -> None:
    # create project
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Sec Proj"},
    )
    assert p.status_code == 201
    project_id = p.json()["id"]

    # should not 500
    r = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/tasks",
        headers=auth_headers(user_token),
        params={"q": "' OR 1=1 --"},
    )
    assert r.status_code == 200, r.text


@pytest.mark.security
def test_gateway_escapes_task_title_against_xss(urls, client, user_token) -> None:
    gateway = urls["gateway"]

    # set cookie for gateway
    client.cookies.set("access_token", user_token)

    # create project via gateway
    pr = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/projects",
        data={"name": "XSS Proj"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert pr.status_code == 200

    # fetch projects page to get project id
    projects_page = httpx_request_with_allure(client, "GET", f"{gateway}/projects")
    assert projects_page.status_code == 200

    import re

    m = re.search(r"/projects/(\d+)\"", projects_page.text)
    assert m is not None
    project_id = int(m.group(1))

    xss = "<script>alert(1)</script>"

    # create task via gateway
    _ = httpx_request_with_allure(
        client,
        "POST",
        f"{gateway}/projects/{project_id}/tasks",
        data={"title": xss, "description": "", "priority": "medium", "tags": ""},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    # open project page and ensure script tag is not present verbatim
    detail = httpx_request_with_allure(client, "GET", f"{gateway}/projects/{project_id}")
    assert detail.status_code == 200

    attach_text("project_html", detail.text[:2000])
    assert "<script>" not in detail.text.lower()
    assert "&lt;script" in detail.text.lower()
