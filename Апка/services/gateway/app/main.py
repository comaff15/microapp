from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import httpx

app = FastAPI(title="Gateway")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

USERS_URL = os.getenv("USERS_URL", "http://localhost:8001")
TASKS_URL = os.getenv("TASKS_URL", "http://localhost:8002")
AUDIT_URL = os.getenv("AUDIT_URL", "http://localhost:8003")
NOTIFIER_URL = os.getenv("NOTIFIER_URL", "http://localhost:8004")


async def _get_current_user(request: Request) -> dict | None:
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{USERS_URL}/users/me", headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            return None
        return r.json()
    except httpx.HTTPError:
        return None


async def _require_admin(request: Request) -> dict:
    current_user = await _get_current_user(request)
    if current_user is None:
        return None
    if current_user.get("role") != "admin":
        return {"__forbidden__": True, **current_user}
    return current_user


def _auth_headers(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=303)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    current_user = await _get_current_user(request)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": current_user,
        },
    )


@app.get("/admin/status", response_class=HTMLResponse)
async def admin_status(request: Request):
    current_user = await _require_admin(request)
    if current_user is None:
        return _redirect("/login")
    if current_user.get("__forbidden__"):
        return templates.TemplateResponse(
            "forbidden.html", {"request": request, "current_user": current_user}
        )

    async with httpx.AsyncClient(timeout=2.0) as client:
        users_r = await client.get(f"{USERS_URL}/health")
        tasks_r = await client.get(f"{TASKS_URL}/health")
        audit_r = await client.get(f"{AUDIT_URL}/health")
        notifier_r = await client.get(f"{NOTIFIER_URL}/health")

    def _safe_json(r: httpx.Response) -> dict:
        try:
            return r.json()
        except Exception:
            return {"status": "unknown"}

    return templates.TemplateResponse(
        "admin_status.html",
        {
            "request": request,
            "current_user": current_user,
            "users": {"http_status": users_r.status_code, **_safe_json(users_r)},
            "tasks": {"http_status": tasks_r.status_code, **_safe_json(tasks_r)},
            "audit": {"http_status": audit_r.status_code, **_safe_json(audit_r)},
            "notifier": {"http_status": notifier_r.status_code, **_safe_json(notifier_r)},
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    current_user = await _get_current_user(request)
    if current_user is not None:
        return _redirect("/projects")
    return templates.TemplateResponse("login.html", {"request": request, "current_user": None, "error": None})


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(f"{USERS_URL}/auth/login", json={"email": email, "password": password})

    if r.status_code != 200:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "current_user": None, "error": "Invalid credentials"},
        )

    token = r.json()["access_token"]
    resp = _redirect("/projects")
    resp.set_cookie("access_token", token, httponly=True, samesite="lax")
    return resp


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    current_user = await _get_current_user(request)
    if current_user is not None:
        return _redirect("/projects")
    return templates.TemplateResponse(
        "register.html", {"request": request, "current_user": None, "error": None}
    )


@app.post("/register")
async def register(request: Request, email: str = Form(...), password: str = Form(...)):
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(f"{USERS_URL}/auth/register", json={"email": email, "password": password})

    if r.status_code not in (200, 201):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "current_user": None, "error": "Registration failed"},
        )

    return _redirect("/login")


@app.post("/logout")
async def logout():
    resp = _redirect("/")
    resp.delete_cookie("access_token")
    return resp


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{TASKS_URL}/projects", headers=_auth_headers(request))

    projects = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse(
        "projects.html",
        {"request": request, "current_user": current_user, "projects": projects, "error": None},
    )


@app.post("/projects", response_class=HTMLResponse)
async def projects_create(request: Request, name: str = Form(...)):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        _ = await client.post(
            f"{TASKS_URL}/projects",
            json={"name": name},
            headers=_auth_headers(request),
        )
        r = await client.get(f"{TASKS_URL}/projects", headers=_auth_headers(request))

    projects = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse(
        "projects_table.html",
        {"request": request, "current_user": current_user, "projects": projects},
    )


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: int):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        pr = await client.get(f"{TASKS_URL}/projects/{project_id}", headers=_auth_headers(request))
        tr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks", headers=_auth_headers(request)
        )

    if pr.status_code != 200:
        return _redirect("/projects")

    project = pr.json()
    tasks = tr.json() if tr.status_code == 200 else []

    return templates.TemplateResponse(
        "project_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "project": project,
            "tasks": tasks,
            "filters": {"status": "", "priority": "", "q": "", "tag": "", "include_archived": ""},
            "error": None,
        },
    )


@app.get("/projects/{project_id}/members", response_class=HTMLResponse)
async def project_members_page(request: Request, project_id: int):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        pr = await client.get(f"{TASKS_URL}/projects/{project_id}", headers=_auth_headers(request))
        mr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/members", headers=_auth_headers(request)
        )

    if pr.status_code != 200:
        return _redirect("/projects")

    project = pr.json()
    members = mr.json() if mr.status_code == 200 else []
    error = None
    if mr.status_code not in (200,):
        error = "Unable to load members"

    return templates.TemplateResponse(
        "project_members.html",
        {
            "request": request,
            "current_user": current_user,
            "project": project,
            "members": members,
            "error": error,
            "members_error": None,
        },
    )


@app.post("/projects/{project_id}/members", response_class=HTMLResponse)
async def project_members_add(
    request: Request, project_id: int, user_email: str = Form(...), role: str = Form("viewer")
):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    members_error = None
    async with httpx.AsyncClient(timeout=5.0) as client:
        rr = await client.post(
            f"{TASKS_URL}/projects/{project_id}/members",
            json={"user_email": user_email, "role": role},
            headers=_auth_headers(request),
        )
        if rr.status_code >= 400:
            try:
                members_error = rr.json().get("detail")
            except Exception:
                members_error = "Failed to update members"
        mr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/members", headers=_auth_headers(request)
        )
        pr = await client.get(f"{TASKS_URL}/projects/{project_id}", headers=_auth_headers(request))

    members = mr.json() if mr.status_code == 200 else []
    project = pr.json() if pr.status_code == 200 else {"id": project_id, "name": ""}

    return templates.TemplateResponse(
        "project_members_table.html",
        {
            "request": request,
            "current_user": current_user,
            "project": project,
            "members": members,
            "members_error": members_error,
        },
    )


@app.post("/projects/{project_id}/members/remove", response_class=HTMLResponse)
async def project_members_remove(request: Request, project_id: int, user_email: str = Form(...)):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    members_error = None
    async with httpx.AsyncClient(timeout=5.0) as client:
        rr = await client.delete(
            f"{TASKS_URL}/projects/{project_id}/members/{user_email}", headers=_auth_headers(request)
        )
        if rr.status_code >= 400:
            try:
                members_error = rr.json().get("detail")
            except Exception:
                members_error = "Failed to remove member"
        mr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/members", headers=_auth_headers(request)
        )
        pr = await client.get(f"{TASKS_URL}/projects/{project_id}", headers=_auth_headers(request))

    members = mr.json() if mr.status_code == 200 else []
    project = pr.json() if pr.status_code == 200 else {"id": project_id, "name": ""}

    return templates.TemplateResponse(
        "project_members_table.html",
        {
            "request": request,
            "current_user": current_user,
            "project": project,
            "members": members,
            "members_error": members_error,
        },
    )


@app.post("/projects/{project_id}/members/transfer", response_class=HTMLResponse)
async def project_members_transfer(request: Request, project_id: int, new_owner_email: str = Form(...)):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    members_error = None
    async with httpx.AsyncClient(timeout=5.0) as client:
        rr = await client.post(
            f"{TASKS_URL}/projects/{project_id}/members/transfer",
            json={"new_owner_email": new_owner_email},
            headers=_auth_headers(request),
        )
        if rr.status_code >= 400:
            try:
                members_error = rr.json().get("detail")
            except Exception:
                members_error = "Failed to transfer ownership"

        mr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/members", headers=_auth_headers(request)
        )
        pr = await client.get(f"{TASKS_URL}/projects/{project_id}", headers=_auth_headers(request))

    members = mr.json() if mr.status_code == 200 else []
    project = pr.json() if pr.status_code == 200 else {"id": project_id, "name": ""}

    return templates.TemplateResponse(
        "project_members_table.html",
        {
            "request": request,
            "current_user": current_user,
            "project": project,
            "members": members,
            "members_error": members_error,
        },
    )


@app.get("/projects/{project_id}/tasks", response_class=HTMLResponse)
async def tasks_table(
    request: Request,
    project_id: int,
    status: str = "",
    priority: str = "",
    q: str = "",
    tag: str = "",
    include_archived: str = "",
):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    params: dict = {}
    if status:
        params["status_filter"] = status
    if priority:
        params["priority"] = priority
    if q:
        params["q"] = q
    if tag:
        params["tag"] = tag
    if include_archived:
        params["include_archived"] = True

    async with httpx.AsyncClient(timeout=5.0) as client:
        tr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks",
            headers=_auth_headers(request),
            params=params,
        )

    tasks = tr.json() if tr.status_code == 200 else []
    return templates.TemplateResponse(
        "tasks_table.html",
        {"request": request, "current_user": current_user, "tasks": tasks},
    )


@app.post("/projects/{project_id}/tasks/{task_id}/archive", response_class=HTMLResponse)
async def task_archive(request: Request, project_id: int, task_id: int):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        _ = await client.post(
            f"{TASKS_URL}/projects/{project_id}/tasks/{task_id}/archive",
            headers=_auth_headers(request),
        )
        tr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks",
            headers=_auth_headers(request),
            params={"include_archived": True},
        )

    tasks = tr.json() if tr.status_code == 200 else []
    return templates.TemplateResponse(
        "tasks_table.html",
        {"request": request, "current_user": current_user, "tasks": tasks},
    )


@app.post("/projects/{project_id}/tasks/{task_id}/restore", response_class=HTMLResponse)
async def task_restore(request: Request, project_id: int, task_id: int):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        _ = await client.post(
            f"{TASKS_URL}/projects/{project_id}/tasks/{task_id}/restore",
            headers=_auth_headers(request),
        )
        tr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks",
            headers=_auth_headers(request),
            params={"include_archived": True},
        )

    tasks = tr.json() if tr.status_code == 200 else []
    return templates.TemplateResponse(
        "tasks_table.html",
        {"request": request, "current_user": current_user, "tasks": tasks},
    )


@app.get("/projects/{project_id}/tasks/{task_id}/row", response_class=HTMLResponse)
async def task_row(request: Request, project_id: int, task_id: int):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks/{task_id}",
            headers=_auth_headers(request),
        )

    if r.status_code != 200:
        return templates.TemplateResponse(
            "task_row.html",
            {"request": request, "current_user": current_user, "t": {"id": task_id, "project_id": project_id, "title": "<missing>", "description": None, "status": "todo", "priority": "medium"}},
        )

    t = r.json()
    return templates.TemplateResponse(
        "task_row.html",
        {"request": request, "current_user": current_user, "t": t},
    )


@app.get("/projects/{project_id}/tasks/{task_id}/edit", response_class=HTMLResponse)
async def task_row_edit(request: Request, project_id: int, task_id: int):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks/{task_id}",
            headers=_auth_headers(request),
        )

    if r.status_code != 200:
        return _redirect(f"/projects/{project_id}")

    t = r.json()
    return templates.TemplateResponse(
        "task_row_edit.html",
        {"request": request, "current_user": current_user, "t": t},
    )


@app.post("/projects/{project_id}/tasks/{task_id}/edit", response_class=HTMLResponse)
async def task_row_edit_submit(
    request: Request,
    project_id: int,
    task_id: int,
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("medium"),
    tags: str = Form(""),
):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.patch(
            f"{TASKS_URL}/projects/{project_id}/tasks/{task_id}",
            json={
                "title": title,
                "description": description or None,
                "priority": priority,
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
            },
            headers=_auth_headers(request),
        )

    if r.status_code != 200:
        return _redirect(f"/projects/{project_id}")

    t = r.json()
    return templates.TemplateResponse(
        "task_row.html",
        {"request": request, "current_user": current_user, "t": t},
    )


@app.post("/projects/{project_id}/tasks", response_class=HTMLResponse)
async def task_create(
    request: Request,
    project_id: int,
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("medium"),
    tags: str = Form(""),
):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        _ = await client.post(
            f"{TASKS_URL}/projects/{project_id}/tasks",
            json={
                "title": title,
                "description": description or None,
                "priority": priority,
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
            },
            headers=_auth_headers(request),
        )
        tr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks", headers=_auth_headers(request)
        )

    tasks = tr.json() if tr.status_code == 200 else []
    return templates.TemplateResponse(
        "tasks_table.html",
        {"request": request, "current_user": current_user, "tasks": tasks},
    )


@app.post("/projects/{project_id}/tasks/{task_id}/status", response_class=HTMLResponse)
async def task_change_status(request: Request, project_id: int, task_id: int, status: str = Form(...)):
    current_user = await _get_current_user(request)
    if current_user is None:
        return _redirect("/login")

    async with httpx.AsyncClient(timeout=5.0) as client:
        _ = await client.patch(
            f"{TASKS_URL}/projects/{project_id}/tasks/{task_id}",
            json={"status": status},
            headers=_auth_headers(request),
        )
        tr = await client.get(
            f"{TASKS_URL}/projects/{project_id}/tasks", headers=_auth_headers(request)
        )

    tasks = tr.json() if tr.status_code == 200 else []
    return templates.TemplateResponse(
        "tasks_table.html",
        {"request": request, "current_user": current_user, "tasks": tasks},
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    current_user = await _require_admin(request)
    if current_user is None:
        return _redirect("/login")
    if current_user.get("__forbidden__"):
        return templates.TemplateResponse("forbidden.html", {"request": request, "current_user": current_user})
    return templates.TemplateResponse("admin.html", {"request": request, "current_user": current_user})


@app.get("/admin/audit", response_class=HTMLResponse)
async def admin_audit(
    request: Request,
    limit: int = 50,
    routing_key: str | None = None,
    before_id: int | None = None,
):
    current_user = await _require_admin(request)
    if current_user is None:
        return _redirect("/login")
    if current_user.get("__forbidden__"):
        return templates.TemplateResponse("forbidden.html", {"request": request, "current_user": current_user})

    params: dict = {"limit": max(1, min(limit, 500))}
    if routing_key:
        params["routing_key"] = routing_key
    if before_id is not None:
        params["before_id"] = before_id

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{AUDIT_URL}/events", params=params)

    events = r.json() if r.status_code == 200 else []

    is_htmx = request.headers.get("hx-request") == "true"
    if is_htmx:
        return templates.TemplateResponse(
            "admin_audit_table.html",
            {
                "request": request,
                "current_user": current_user,
                "events": events,
                "limit": params["limit"],
                "routing_key": routing_key,
            },
        )

    return templates.TemplateResponse(
        "admin_audit.html",
        {
            "request": request,
            "current_user": current_user,
            "events": events,
            "limit": params["limit"],
            "routing_key": routing_key,
        },
    )


@app.get("/admin/notifications", response_class=HTMLResponse)
async def admin_notifications(
    request: Request,
    limit: int = 50,
    status: str | None = None,
    before_id: int | None = None,
):
    current_user = await _require_admin(request)
    if current_user is None:
        return _redirect("/login")
    if current_user.get("__forbidden__"):
        return templates.TemplateResponse("forbidden.html", {"request": request, "current_user": current_user})

    params: dict = {"limit": max(1, min(limit, 500))}
    if status:
        params["status"] = status
    if before_id is not None:
        params["before_id"] = before_id

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{NOTIFIER_URL}/notifications", params=params)

    notifications = r.json() if r.status_code == 200 else []

    is_htmx = request.headers.get("hx-request") == "true"
    if is_htmx:
        return templates.TemplateResponse(
            "admin_notifications_table.html",
            {
                "request": request,
                "current_user": current_user,
                "notifications": notifications,
                "limit": params["limit"],
                "status": status,
            },
        )

    return templates.TemplateResponse(
        "admin_notifications.html",
        {
            "request": request,
            "current_user": current_user,
            "notifications": notifications,
            "limit": params["limit"],
            "status": status,
        },
    )


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, limit: int = 50, before_id: int | None = None):
    current_user = await _require_admin(request)
    if current_user is None:
        return _redirect("/login")
    if current_user.get("__forbidden__"):
        return templates.TemplateResponse("forbidden.html", {"request": request, "current_user": current_user})

    params: dict = {"limit": max(1, min(limit, 500))}
    if before_id is not None:
        params["before_id"] = before_id

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{USERS_URL}/admin/users", params=params, headers=_auth_headers(request))

    users = r.json() if r.status_code == 200 else []

    is_htmx = request.headers.get("hx-request") == "true"
    if is_htmx:
        return templates.TemplateResponse(
            "admin_users_table.html",
            {"request": request, "current_user": current_user, "users": users, "limit": params["limit"]},
        )

    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "current_user": current_user, "users": users, "limit": params["limit"]},
    )


@app.post("/admin/users/{user_id}", response_class=HTMLResponse)
async def admin_user_patch(
    request: Request,
    user_id: int,
    role: str = Form(""),
    is_active: str = Form(""),
):
    current_user = await _require_admin(request)
    if current_user is None:
        return _redirect("/login")
    if current_user.get("__forbidden__"):
        return templates.TemplateResponse("forbidden.html", {"request": request, "current_user": current_user})

    payload: dict = {}
    if role:
        payload["role"] = role
    if is_active:
        payload["is_active"] = is_active.lower() in ("1", "true", "yes", "on")

    async with httpx.AsyncClient(timeout=5.0) as client:
        _ = await client.patch(
            f"{USERS_URL}/admin/users/{user_id}",
            json=payload,
            headers=_auth_headers(request),
        )
        r = await client.get(f"{USERS_URL}/admin/users", params={"limit": 50}, headers=_auth_headers(request))

    users = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse(
        "admin_users_table.html",
        {"request": request, "current_user": current_user, "users": users, "limit": 50},
    )
