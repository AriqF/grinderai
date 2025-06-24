from typing import Optional
from datetime import datetime
from app.schemas.user_schema import UserCreate
from motor.motor_asyncio import AsyncIOMotorDatabase


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["users"]

    async def create_user(self, user: UserCreate):
        data = {
            "_id": user.telegram_id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "long_term_goals": user.long_term_goals or [],
            "current_level": 1,
            "exp_points": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        await self.collection.insert_one(data)
        return data

    async def get_user_by_id(self, telegram_id: str) -> Optional[dict]:
        return await self.collection.find_one({"_id": telegram_id})

    async def update_goals(self, telegram_id: str, new_goals: list):
        result = await self.collection.update_one(
            {"_id": telegram_id}, {"$set": {"long_term_goals": new_goals}}
        )
        return result.modified_count > 0
