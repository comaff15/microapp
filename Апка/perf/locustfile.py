import os
import random
import uuid

from locust import HttpUser, task, between


class GatewayUser(HttpUser):
    wait_time = between(0.2, 1.2)

    def on_start(self):
        self.base = os.environ.get("GATEWAY_URL", "http://localhost:8000")

    @task(2)
    def open_home(self):
        self.client.get("/")

    @task(3)
    def open_login(self):
        self.client.get("/login")

    @task(1)
    def open_projects(self):
        # will be 303 if not logged in; still useful for baseline
        self.client.get("/projects", allow_redirects=False)


class TasksApiUser(HttpUser):
    host = os.environ.get("TASKS_URL", "http://localhost:8002")
    wait_time = between(0.1, 0.8)

    def on_start(self):
        self.users_url = os.environ.get("USERS_URL", "http://localhost:8001")
        self.token = None
        self.project_id = None
        self.task_id = None

        email = f"locust-{uuid.uuid4().hex[:10]}@example.com"
        password = "password123"

        # Register
        self.client.post(
            f"{self.users_url}/auth/register",
            json={"email": email, "password": password},
            name="users_register",
        )

        # Login
        r = self.client.post(
            f"{self.users_url}/auth/login",
            json={"email": email, "password": password},
            name="users_login",
        )
        if r.status_code == 200:
            self.token = r.json().get("access_token")

    @task(5)
    def health(self):
        self.client.get("/health")

    @task(2)
    def list_projects_unauth(self):
        self.client.get("/projects", headers={})

    @task(2)
    def list_tasks_unauth(self):
        project_id = random.randint(1, 3)
        self.client.get(f"/projects/{project_id}/tasks", headers={})

    @task(3)
    def auth_flow_create_project_and_task(self):
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        if not self.project_id:
            r = self.client.post("/projects", json={"name": "Load"}, headers=headers, name="tasks_create_project")
            if r.status_code in (200, 201):
                self.project_id = r.json().get("id")
            return

        if not self.task_id:
            r = self.client.post(
                f"/projects/{self.project_id}/tasks",
                json={"title": "LoadTask", "description": "", "priority": "low", "tags": ["load"]},
                headers=headers,
                name="tasks_create_task",
            )
            if r.status_code in (200, 201):
                self.task_id = r.json().get("id")
            return

        self.client.get(f"/projects/{self.project_id}/tasks", headers=headers, name="tasks_list_tasks")

    @task(1)
    def auth_patch_task(self):
        if not (self.token and self.project_id and self.task_id):
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.patch(
            f"/projects/{self.project_id}/tasks/{self.task_id}",
            json={"title": "LoadTaskUpdated"},
            headers=headers,
            name="tasks_patch_task",
        )
