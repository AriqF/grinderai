from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "rune_ai")

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]


async def get_database():
    return db
