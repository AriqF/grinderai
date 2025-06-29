from fastapi import FastAPI
from dotenv import load_dotenv
import os

from app.db.mongo import connect_to_mongo
from app.routers import user_router, goal_router
from app.utils.bot_handler import configure_bot
from contextlib import asynccontextmanager

load_dotenv()


app = FastAPI(title="Rune Assistant Bot API")

# Register routers
app.include_router(user_router.router, prefix="/users", tags=["Users"])
app.include_router(goal_router.router, prefix="/goals", tags=["Goals"])


@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()
    await configure_bot()


@app.get("/")
async def root():
    return {"message": "Rune Assistant Bot API is running."}
