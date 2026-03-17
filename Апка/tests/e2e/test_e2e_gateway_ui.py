import re

import pytest

from tests.helpers import attach_text, ui_stage


def _extract_first_int(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    assert m is not None, f"Pattern not found: {pattern}"
    return int(m.group(1))


def _register_and_login(page, gateway: str, email: str) -> None:
    with ui_stage(page, "register"):
        page.goto(f"{gateway}/register", wait_until="domcontentloaded")
        page.fill('input[name="email"]', email)
        page.fill('input[name="password"]', "password123")
        page.click('button[type="submit"]')
        page.wait_for_url(re.compile(r".*/login$"))

    with ui_stage(page, "login"):
        page.fill('input[name="email"]', email)
        page.fill('input[name="password"]', "password123")
        page.click('button[type="submit"]')
        page.wait_for_url(re.compile(r".*/projects$"))


def _create_project(page, gateway: str, name: str) -> int:
    with ui_stage(page, "create_project"):
        page.fill('input[name="name"]', name)
        page.click('form[hx-post="/projects"] button[type="submit"]')
        page.wait_for_selector("#projects-table tbody tr a[href^='/projects/']")

        href = page.locator("#projects-table tbody tr a").first.get_attribute("href")
        assert href is not None
        return _extract_first_int(r"/projects/(\d+)$", href)


def _open_project(page, gateway: str, project_id: int) -> None:
    with ui_stage(page, "open_project"):
        page.goto(f"{gateway}/projects/{project_id}", wait_until="domcontentloaded")
        page.wait_for_selector("#tasks-table")


def _create_task(page, project_id: int, *, title: str, tags: str = "") -> int:
    with ui_stage(page, "create_task"):
        page.fill('input[name="title"]', title)
        page.fill('input[name="tags"]', tags)
        page.click(f'form[hx-post="/projects/{project_id}/tasks"] button[type="submit"]')
        page.wait_for_selector("#tasks-table tbody tr[id^='task-row-']")

        row_id = page.locator("#tasks-table tbody tr[id^='task-row-']").first.get_attribute("id")
        assert row_id is not None
        return _extract_first_int(r"task-row-(\d+)$", row_id)


@pytest.mark.e2e
def test_gateway_ui_register_login_create_project_and_task(page, urls, unique_email) -> None:
    gateway = urls["gateway"]

    _register_and_login(page, gateway, unique_email)

    # Create project (HTMX updates table)
    project_id = _create_project(page, gateway, "E2E Проект")
    attach_text("project_id", str(project_id))

    # Open project
    _open_project(page, gateway, project_id)

    # Create task
    task_id = _create_task(page, project_id, title="E2E Задача", tags="e2e,ui")
    attach_text("task_id", str(task_id))

    # Archive and restore through buttons
    with ui_stage(page, "archive_task"):
        page.locator(f"#task-row-{task_id} button.danger").first.click()
        page.wait_for_timeout(300)
    with ui_stage(page, "restore_task"):
        page.locator(f"#task-row-{task_id} button.success").first.click()
        page.wait_for_timeout(300)


@pytest.mark.e2e
def test_gateway_ui_edit_task_inline(page, urls, unique_email) -> None:
    gateway = urls["gateway"]
    _register_and_login(page, gateway, unique_email)
    project_id = _create_project(page, gateway, "E2E Edit")
    _open_project(page, gateway, project_id)

    task_id = _create_task(page, project_id, title="Old Title", tags="x")
    attach_text("task_id", str(task_id))

    with ui_stage(page, "edit_task_open"):
        page.locator(f"#task-row-{task_id} button", has_text="Править").click()
        page.wait_for_selector(f"#task-row-{task_id} form")
    with ui_stage(page, "edit_task_save"):
        page.fill(f"#task-row-{task_id} input[name='title']", "New Title")
        page.click(f"#task-row-{task_id} button.primary")
        page.wait_for_selector(f"#task-row-{task_id} td:has-text('New Title')")


@pytest.mark.e2e
def test_gateway_ui_task_status_flow(page, urls, unique_email) -> None:
    gateway = urls["gateway"]
    _register_and_login(page, gateway, unique_email)
    project_id = _create_project(page, gateway, "E2E Status")
    _open_project(page, gateway, project_id)

    task_id = _create_task(page, project_id, title="Status Task", tags="")
    attach_text("task_id", str(task_id))

    with ui_stage(page, "status_start"):
        page.locator(f"#task-row-{task_id} button.primary", has_text="Старт").click()
        page.wait_for_selector(f"#task-row-{task_id} td span.badge:has-text('in_progress')")

    with ui_stage(page, "status_done"):
        page.locator(f"#task-row-{task_id} button.success", has_text="Готово").click()
        page.wait_for_selector(f"#task-row-{task_id} td span.badge:has-text('done')")


@pytest.mark.e2e
def test_gateway_ui_filters_and_archived_visibility(page, urls, unique_email) -> None:
    gateway = urls["gateway"]
    _register_and_login(page, gateway, unique_email)
    project_id = _create_project(page, gateway, "E2E Filters")
    _open_project(page, gateway, project_id)

    t1 = _create_task(page, project_id, title="Alpha", tags="red")
    t2 = _create_task(page, project_id, title="Beta", tags="blue")
    attach_text("t1", str(t1))
    attach_text("t2", str(t2))

    with ui_stage(page, "archive_beta"):
        page.locator(f"#task-row-{t2} button.danger", has_text="В архив").click()
        page.wait_for_timeout(300)

    with ui_stage(page, "filter_q_alpha"):
        page.fill("form[hx-get] input[name='q']", "Alpha")
        page.click("form[hx-get] button.primary")
        page.wait_for_selector(f"#task-row-{t1}")
        page.wait_for_selector(f"#task-row-{t2}", state="detached")
        assert page.locator(f"#task-row-{t2}").count() == 0

    with ui_stage(page, "filter_include_archived"):
        page.fill("form[hx-get] input[name='q']", "")
        page.check("form[hx-get] input[name='include_archived']")
        page.click("form[hx-get] button.primary")
        page.wait_for_selector(f"#task-row-{t2}")
