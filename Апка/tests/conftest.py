import os
import time
import uuid
import json

import pathlib

import allure
import httpx
import pytest

from tests.helpers import env_url


def _wait_for(url: str, timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None

    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.5)

    if last_err is not None:
        raise RuntimeError(f"Service not ready: {url}; last error={last_err}")
    raise RuntimeError(f"Service not ready: {url}")


@pytest.fixture(scope="session")
def urls() -> dict[str, str]:
    return {
        "gateway": env_url("GATEWAY_URL"),
        "users": env_url("USERS_URL"),
        "tasks": env_url("TASKS_URL"),
        "audit": env_url("AUDIT_URL"),
        "notifier": os.environ.get("NOTIFIER_URL", ""),
    }


@pytest.fixture(scope="session", autouse=True)
def wait_for_services(urls: dict[str, str]) -> None:
    _wait_for(f"{urls['gateway']}/health", timeout_s=90)
    _wait_for(f"{urls['users']}/health", timeout_s=90)
    _wait_for(f"{urls['tasks']}/health", timeout_s=90)
    _wait_for(f"{urls['audit']}/health", timeout_s=90)
    if urls.get("notifier"):
        _wait_for(f"{urls['notifier']}/health", timeout_s=90)


@pytest.fixture(scope="session", autouse=True)
def _allure_environment(urls: dict[str, str]) -> None:
    results_dir = pathlib.Path("/app/allure-results")
    results_dir.mkdir(parents=True, exist_ok=True)

    env_lines = [
        f"GATEWAY_URL={urls.get('gateway','')}",
        f"USERS_URL={urls.get('users','')}",
        f"TASKS_URL={urls.get('tasks','')}",
        f"AUDIT_URL={urls.get('audit','')}",
        f"NOTIFIER_URL={urls.get('notifier','')}",
        f"PYTHON={os.environ.get('PYTHON_VERSION','')}",
    ]
    (results_dir / "environment.properties").write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    executor = {
        "name": "docker-compose",
        "type": "local",
        "buildName": os.environ.get("CI_BUILD", "local"),
        "buildUrl": os.environ.get("CI_URL", ""),
    }
    (results_dir / "executor.json").write_text(json.dumps(executor, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture()
def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture()
def client() -> httpx.Client:
    with httpx.Client(timeout=10.0) as c:
        yield c


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
    if rep.when != "call":
        return
    if rep.failed:
        allure.attach(str(rep.longrepr), name="failure", attachment_type=allure.attachment_type.TEXT)


@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "record_video_dir": "/app/allure-results/videos",
    }


@pytest.fixture(autouse=True)
def _playwright_auto_attach_on_failure(request):
    yield
    rep = getattr(request.node, "rep_call", None)
    page = request.node.funcargs.get("page") if hasattr(request.node, "funcargs") else None
    if page is None:
        return
    try:
        png = page.screenshot(full_page=True)
        allure.attach(png, name="screenshot.final", attachment_type=allure.attachment_type.PNG)
        try:
            html = page.content()
            allure.attach(html, name="page.html", attachment_type=allure.attachment_type.HTML)
        except Exception:
            pass

        if rep is not None and rep.failed:
            allure.attach(png, name="screenshot.failure", attachment_type=allure.attachment_type.PNG)

        # Video (if enabled by browser_context_args)
        try:
            v = page.video
            if v is not None:
                video_path = v.path()
                if video_path and os.path.exists(video_path):
                    with open(video_path, "rb") as f:
                        allure.attach(f.read(), name="video.webm", attachment_type=allure.attachment_type.WEBM)
        except Exception:
            pass

        # Trace (if enabled via PLAYWRIGHT_TRACE=1 and context.tracing started)
        try:
            trace_path = getattr(request.node, "_pw_trace_path", None)
            if trace_path and os.path.exists(trace_path):
                with open(trace_path, "rb") as f:
                    allure.attach(f.read(), name="trace.zip", attachment_type=allure.attachment_type.ZIP)
        except Exception:
            pass
    except Exception:
        return


@pytest.fixture(autouse=True)
def _playwright_trace_control(request):
    # Enable tracing only for Playwright tests (when context fixture exists)
    context = request.node.funcargs.get("context") if hasattr(request.node, "funcargs") else None
    if context is None:
        yield
        return

    trace_dir = pathlib.Path("/app/allure-results/traces")
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = str(trace_dir / f"trace-{request.node.nodeid.replace(os.sep, '_').replace('::','_')}.zip")
    setattr(request.node, "_pw_trace_path", trace_path)

    try:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
    except Exception:
        yield
        return

    yield

    try:
        context.tracing.stop(path=trace_path)
    except Exception:
        return


def _login(users_url: str, email: str, password: str) -> str:
    r = httpx.post(f"{users_url}/auth/login", json={"email": email, "password": password}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(urls: dict[str, str]) -> str:
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@local.ru")
    admin_password = os.environ.get("ADMIN_PASSWORD", "adminadmin")
    return _login(urls["users"], admin_email, admin_password)


@pytest.fixture()
def user_token(urls: dict[str, str]) -> str:
    unique_email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    password = "password123"
    r = httpx.post(
        f"{urls['users']}/auth/register",
        json={"email": unique_email, "password": password},
        timeout=10.0,
    )
    assert r.status_code in (200, 201), r.text
    return _login(urls["users"], unique_email, password)
