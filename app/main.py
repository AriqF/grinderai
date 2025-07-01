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
    ask_daily_share,
    analyze_daily_sentiment,
)
import pytz

load_dotenv()

app = FastAPI(title="Rune Assistant Bot API")
scheduler = AsyncIOScheduler()

# Register routers
app.include_router(user_router.router, prefix="/users", tags=["Users"])
app.include_router(goal_router.router, prefix="/goals", tags=["Goals"])


@app.on_event("startup")
async def startup_event():
    tz = pytz.timezone("Asia/Jakarta")
    await connect_to_mongo()
    await configure_bot()
    # scheduler.add_job(test_cron_job, CronTrigger(second="*/10"))
    scheduler.add_job(remind_user_tasks, CronTrigger(hour=6, timezone=tz))
    scheduler.add_job(remind_user_tasks, CronTrigger(hour=20, timezone=tz))
    scheduler.add_job(remind_user_tasks, CronTrigger(hour=9, minute=55, timezone=tz))
    scheduler.add_job(remind_user_tasks, CronTrigger(hour=12, timezone=tz))
    # scheduler.add_job(remind_user_tasks, CronTrigger(minute="*/1", timezone=tz))
    scheduler.add_job(
        daily_progress_creation,
        CronTrigger(hour=0, timezone=tz),
    )
    scheduler.add_job(ask_daily_share, CronTrigger(hour=20, minute=15, timezone=tz))
    scheduler.add_job(
        analyze_daily_sentiment, CronTrigger(hour=1, minute=30, timezone=tz)
    )
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    print("[Scheduler] Shutdown")


@app.get("/")
async def root():
    return {"message": "Rune Assistant Bot API is running."}
