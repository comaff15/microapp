import json
import os
import time
import contextlib
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import allure
import httpx


def attach_json(name: str, data: Any) -> None:
    try:
        allure.attach(json.dumps(data, ensure_ascii=False, indent=2), name=name, attachment_type=allure.attachment_type.JSON)
    except Exception:
        allure.attach(str(data), name=name, attachment_type=allure.attachment_type.TEXT)


def attach_text(name: str, text: str) -> None:
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_png(name: str, png_bytes: bytes) -> None:
    allure.attach(png_bytes, name=name, attachment_type=allure.attachment_type.PNG)


def attach_html(name: str, html: str) -> None:
    allure.attach(html, name=name, attachment_type=allure.attachment_type.HTML)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def eventually(
    fn: Callable[[], Any],
    timeout_s: float = 12.0,
    interval_s: float = 0.5,
    retry_on: tuple[type[BaseException], ...] = (AssertionError,),
) -> Any:
    deadline = time.time() + timeout_s
    last_err: BaseException | None = None

    while time.time() < deadline:
        try:
            return fn()
        except retry_on as e:  # noqa: PERF203
            last_err = e
            time.sleep(interval_s)

    if last_err is None:
        raise AssertionError("eventually() timed out")
    raise last_err


def env_url(name: str, default: str = "") -> str:
    v = os.environ.get(name, default)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _truncate(s: str, limit: int = 12000) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + "\n...<truncated>..."


def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def _to_curl(method: str, url: str, *, headers: dict[str, str] | None, body: bytes | None) -> str:
    parts: list[str] = ["curl", "-sS", "-X", method.upper(), f"'{url}'"]
    if headers:
        for k, v in headers.items():
            parts.append(f"-H '{k}: {v}'")
    if body:
        try:
            b = body.decode("utf-8")
        except Exception:
            b = body.decode("utf-8", errors="replace")
        parts.append(f"--data-raw '{b}'")
    return " ".join(parts)


@contextlib.contextmanager
def ui_stage(page: Any, name: str):
    with allure.step(name):
        yield
        try:
            png = page.screenshot(full_page=True)
            attach_png(f"ui.{name}.png", png)
        except Exception:
            pass
        try:
            html = page.content()
            attach_html(f"ui.{name}.html", _truncate(html, limit=200000))
        except Exception:
            pass


def httpx_request_with_allure(client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response:
    with allure.step(f"HTTP {method.upper()} {url}"):
        req_headers = dict(kwargs.get("headers") or {})
        params = kwargs.get("params")
        full_url = url
        if params:
            try:
                full_url = url + ("&" if "?" in url else "?") + urlencode(params, doseq=True)
            except Exception:
                full_url = url

        body_bytes: bytes | None = None
        if "json" in kwargs:
            try:
                body_bytes = json.dumps(kwargs.get("json"), ensure_ascii=False).encode("utf-8")
            except Exception:
                body_bytes = None
        elif "data" in kwargs and isinstance(kwargs.get("data"), (str, bytes)):
            d = kwargs.get("data")
            body_bytes = d if isinstance(d, bytes) else d.encode("utf-8")
        elif "content" in kwargs and isinstance(kwargs.get("content"), (str, bytes)):
            c = kwargs.get("content")
            body_bytes = c if isinstance(c, bytes) else c.encode("utf-8")

        attach_text("request.url", full_url)
        attach_text("request.method", method.upper())
        if req_headers:
            attach_json("request.headers", req_headers)
        if body_bytes is not None:
            try:
                attach_text("request.body", _truncate(body_bytes.decode("utf-8", errors="replace")))
            except Exception:
                pass
        attach_text("request.curl", _to_curl(method, full_url, headers=req_headers, body=body_bytes))

        started = time.perf_counter()
        r = client.request(method, url, **kwargs)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        attach_text("response.status", str(r.status_code))
        attach_text("response.elapsed_ms", str(elapsed_ms))
        try:
            attach_json("response.headers", dict(r.headers))
        except Exception:
            pass

        text = r.text
        attach_text("response.text", _truncate(text))
        parsed = _safe_json_loads(text)
        if parsed is not None:
            attach_json("response.json", parsed)
        return r
