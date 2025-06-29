from fastapi import FastAPI
from dotenv import load_dotenv
import os

from app.db.mongo import connect_to_mongo
from app.routers import user_router, goal_router
from app.utils.bot_handler import configure_bot
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.utils.scheduler import (
    test_cron_job,
    remind_user_tasks,
    daily_progress_creation,
)

load_dotenv()

app = FastAPI(title="Rune Assistant Bot API")
scheduler = AsyncIOScheduler()

# Register routers
app.include_router(user_router.router, prefix="/users", tags=["Users"])
app.include_router(goal_router.router, prefix="/goals", tags=["Goals"])


@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()
    await configure_bot()
    # scheduler.add_job(test_cron_job, CronTrigger(second="*/10"))
    scheduler.add_job(remind_user_tasks, CronTrigger(hour=6))
    scheduler.add_job(remind_user_tasks, CronTrigger(hour=20))
    scheduler.add_job(
        daily_progress_creation,
        CronTrigger(
            hour=0,
        ),
    )
    # Todo: auto create progress collection
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    print("[Scheduler] Shutdown")


@app.get("/")
async def root():
    return {"message": "Rune Assistant Bot API is running."}
