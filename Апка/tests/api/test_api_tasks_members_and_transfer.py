import pytest

from tests.helpers import attach_json, auth_headers, httpx_request_with_allure


def _register_and_login(urls, client, email: str) -> str:
    r = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert r.status_code == 201, r.text

    login = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['users']}/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.mark.api
def test_members_add_list_remove_and_transfer_ownership(urls, client, user_token, unique_email) -> None:
    # create project
    p = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects",
        headers=auth_headers(user_token),
        json={"name": "Members Proj"},
    )
    assert p.status_code == 201, p.text
    project_id = p.json()["id"]

    # create second user
    member_email = unique_email
    token2 = _register_and_login(urls, client, member_email)

    # owner adds member
    add = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/members",
        headers=auth_headers(user_token),
        json={"user_email": member_email, "role": "viewer"},
    )
    assert add.status_code == 201, add.text

    # list members
    lst = httpx_request_with_allure(
        client,
        "GET",
        f"{urls['tasks']}/projects/{project_id}/members",
        headers=auth_headers(user_token),
    )
    assert lst.status_code == 200, lst.text
    attach_json("members", lst.json())
    assert any(m["user_email"] == member_email for m in lst.json())

    # non-owner cannot add
    add2 = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/members",
        headers=auth_headers(token2),
        json={"user_email": "x3@example.com", "role": "viewer"},
    )
    assert add2.status_code == 403, add2.text

    # transfer ownership to member2
    transfer = httpx_request_with_allure(
        client,
        "POST",
        f"{urls['tasks']}/projects/{project_id}/members/transfer",
        headers=auth_headers(user_token),
        json={"new_owner_email": member_email},
    )
    assert transfer.status_code == 204, transfer.text

    # old owner now cannot remove members (owner only)
    rm_fail = httpx_request_with_allure(
        client,
        "DELETE",
        f"{urls['tasks']}/projects/{project_id}/members/{member_email}",
        headers=auth_headers(user_token),
    )
    assert rm_fail.status_code == 403, rm_fail.text

    # new owner can remove old owner
    rm = httpx_request_with_allure(
        client,
        "DELETE",
        f"{urls['tasks']}/projects/{project_id}/members/{p.json()['owner_email']}",
        headers=auth_headers(token2),
    )
    assert rm.status_code == 204, rm.text
