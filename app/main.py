from fastapi import FastAPI
from dotenv import load_dotenv
import os

from app.db.mongo import get_database
from app.routers import user_router
from app.utils.bot_handler import configure_bot
from contextlib import asynccontextmanager

load_dotenv()


app = FastAPI(title="Rune Assistant Bot API")

# Register routers
app.include_router(user_router.router, prefix="/users", tags=["Users"])


@app.on_event("startup")
async def startup_event():
    await configure_bot()


@app.get("/")
async def root():
    return {"message": "Rune Assistant Bot API is running."}
