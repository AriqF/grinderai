from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# from app.routers import user_router  # Tambahkan router lain nanti

load_dotenv()

app = FastAPI(title="AI Assistant Bot API")

# MongoDB Connection
# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
# MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "griderai")
# client = AsyncIOMotorClient(MONGO_URI)
# db = client[MONGO_DB_NAME]


# # Dependency to get DB
# async def get_database():
#     return db


# Register routers
# app.include_router(user_router.router, prefix="/users", tags=["Users"])


# Example root endpoint
@app.get("/")
async def root():
    return {"message": "AI Assistant Bot API is running."}
