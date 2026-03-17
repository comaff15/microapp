import os
import asyncio
from fastapi import FastAPI

from sqlalchemy import select

from app.core.config import settings
from app.security import hash_password
from app.db import engine
from app.db import SessionLocal
from app.models import Base
from app.models import User
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import users as users_router

app = FastAPI(title="Users")


async def _wait_for_db_ready() -> None:
    while True:
        try:
            async with engine.connect() as conn:
                await conn.execute(select(1))
            return
        except Exception:
            await asyncio.sleep(1)


@app.on_event("startup")
async def on_startup() -> None:
    await _wait_for_db_ready()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.admin_email and settings.admin_password:
        async with SessionLocal() as session:
            res = await session.execute(select(User).where(User.email == settings.admin_email))
            existing = res.scalar_one_or_none()
            if existing is None:
                session.add(
                    User(
                        email=settings.admin_email,
                        password_hash=hash_password(settings.admin_password),
                        role="admin",
                        is_active=True,
                    )
                )
                await session.commit()


app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(admin_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": os.getenv("SERVICE_NAME", "users")}
