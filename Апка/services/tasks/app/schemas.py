from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectPublic(BaseModel):
    id: int
    name: str
    owner_email: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: str = Field(default="medium")
    tags: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    tags: list[str] | None = None
    is_archived: bool | None = None


class TaskPublic(BaseModel):
    id: int
    project_id: int
    title: str
    description: str | None
    status: str
    priority: str
    tags: list[str] = Field(default_factory=list)
    is_archived: bool = False
