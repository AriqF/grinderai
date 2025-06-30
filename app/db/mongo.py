from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv
from pymongo.errors import ServerSelectionTimeoutError
import os
import logging
from pymongo import ASCENDING

load_dotenv()
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "rune_ai")

# Setup client with short timeout for quick failure
client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=3000)

# Global DB object
db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo():
    global db
    try:
        # Ping the server to check connection
        await client.admin.command("ping")
        db = client[MONGO_DB_NAME]
        logger.info("[MongoDB] Connected successfully.")
        await init_indexes()
    except ServerSelectionTimeoutError as e:
        logger.error(f"[MongoDB] Connection failed: {e}")
        db = None  # or raise custom error


async def get_database() -> AsyncIOMotorDatabase:
    if db is None:
        raise RuntimeError("Database not available")
    return db


async def init_indexes():
    if db is None:
        raise RuntimeError("Database not initialized")

    await db["daily_progress"].create_index(
        [("telegram_id", ASCENDING), ("date", ASCENDING)],
        unique=True,
        name="idx_telegram_date_unique",
    )

    logger.info("[MongoDB] Indexes initialized.")
