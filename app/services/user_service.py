from typing import Optional, List
from datetime import datetime

from fastapi import HTTPException
from app.schemas.user_schema import UserCreate, UserOut, UserBasicInfo
from motor.motor_asyncio import AsyncIOMotorDatabase
from telegram import User
from pymongo import ReturnDocument


class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["users"]

    async def check_and_create(self, user):
        try:
            telegram_id = str(user.id)
            is_exists = await self.check_user(telegram_id)

            if is_exists:
                return {"user": user, "new_created": False}

            await self.create_user(
                {
                    "_id": telegram_id,
                    "telegram_id": telegram_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language": user.language_code,
                    "level": 1,
                    "exp": 0,
                    "created_at": datetime.utcnow(),
                }
            )

            return {"user": user, "new_created": True}

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"check_and_create error: {str(e)}"
            )

    async def check_user(self, telegram_id: str) -> bool:
        try:
            user = await self.collection.find_one({"_id": telegram_id})
            return user is not None
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"check_user error: {str(e)}")

    async def create_user(self, user_data: dict):
        try:
            await self.collection.insert_one(user_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"create_user error: {str(e)}")

    async def get_user_by_id(self, telegram_id: str) -> Optional[dict]:
        doc = await self.collection.find_one({"_id": telegram_id})
        if not doc:
            return None
        return UserBasicInfo(**doc).model_dump(by_alias=True)

    async def update_goals(self, telegram_id: str, new_goals: list):
        result = await self.collection.update_one(
            {"_id": telegram_id}, {"$set": {"long_term_goals": new_goals}}
        )
        return result.modified_count > 0

    async def find_all(self):
        try:
            cursor = self.collection.find()
            user_list = []
            async for doc in cursor:
                user_list.append(UserBasicInfo(**doc).model_dump())
            return user_list
        except Exception as e:
            print("ERROR ", e)
            raise ValueError(e)

    def calculate_level(self, exp: int) -> int:
        return int((exp // 100) + 1)

    async def increase_exp(self, uid: str, amount: int):
        try:
            updated = await self.collection.find_one_and_update(
                {"_id": uid},
                {"$inc": {"exp": amount}},
                return_document=ReturnDocument.AFTER,
            )

            if not updated:
                raise ValueError("Unable to increase user exp")

            new_exp = updated["exp"]
            new_level = self.calculate_level(new_exp)

            if new_level > updated.get("level", 1):
                await self.collection.update_one(
                    {"_id": uid}, {"$set": {"level": new_level}}
                )
            updated["level"] = new_level

            return updated
        except Exception as e:
            print(e)
            raise ValueError(e)
