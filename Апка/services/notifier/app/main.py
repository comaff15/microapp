import asyncio
import os

from fastapi import FastAPI
from sqlalchemy import select

from app.consumer import consumer, wait_for_broker_ready
from app.db import engine
from app.models import Base
from app.routers import notifications as notifications_router

app = FastAPI(title="Notifier")


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

    await wait_for_broker_ready()
    await consumer.connect()
    asyncio.create_task(consumer.run())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await consumer.close()


app.include_router(notifications_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": os.getenv("SERVICE_NAME", "notifier")}
