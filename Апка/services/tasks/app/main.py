import os
import asyncio
from fastapi import FastAPI
from sqlalchemy import select
import aio_pika

from app.broker import publisher
from app.db import engine
from app.models import Base
from app.routers import projects as projects_router
from app.routers import members as members_router
from app.routers import tasks as tasks_router

app = FastAPI(title="Tasks")


@app.on_event("startup")
async def on_startup() -> None:
    while True:
        try:
            async with engine.connect() as conn:
                await conn.execute(select(1))
            break
        except Exception:
            await asyncio.sleep(1)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Wait for RabbitMQ to be ready as well.
    while True:
        try:
            connection = await aio_pika.connect_robust(os.getenv("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/"))
            await connection.close()
            break
        except Exception:
            await asyncio.sleep(1)

    await publisher.connect()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await publisher.close()


app.include_router(projects_router.router)
app.include_router(members_router.router)
app.include_router(tasks_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": os.getenv("SERVICE_NAME", "tasks")}
