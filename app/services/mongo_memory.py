from typing import List, Union
from datetime import datetime
from langchain.schema import BaseChatMessageHistory, HumanMessage, AIMessage
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException
import pymongo


class ChatMemory(BaseChatMessageHistory):
    def __init__(self, db: AsyncIOMotorDatabase, user_id: str):
        # Create a sync MongoDB client for LangChain compatibility
        # Extract connection details from the async client
        self.user_id = user_id
        self._messages = []

        # Create sync client using the same connection string
        # You'll need to pass the MongoDB connection string here
        # For now, we'll store the async db reference and create sync operations
        self.async_collection = db["conversations"]

        # Create sync client (you'll need to modify this based on your MongoDB setup)
        # self.sync_client = pymongo.MongoClient(your_mongo_connection_string)
        # self.sync_collection = self.sync_client[db.name]["conversations"]

    @property
    def messages(self):
        """Sync property required by LangChain"""
        return self._messages

    def add_message(self, message: Union[HumanMessage, AIMessage]) -> None:
        """Sync method required by LangChain - just store in memory"""
        self._messages.append(message)

    def clear(self) -> None:
        """Sync method required by LangChain"""
        self._messages = []

    # Async methods for your application logic
    async def load_messages_from_db(self) -> List[Union[AIMessage, HumanMessage]]:
        """Load messages from database and populate memory"""
        doc = await self.async_collection.find_one({"_id": self.user_id})
        if not doc or "messages" not in doc:
            self._messages = []
            return []

        messages = []
        for m in doc["messages"]:
            if m["type"] == "human":
                messages.append(HumanMessage(content=m["content"]))
            elif m["type"] == "ai":
                messages.append(AIMessage(content=m["content"]))

        self._messages = messages
        return messages

    async def save_messages_to_db(self) -> None:
        """Save current messages to database"""
        if not self._messages:
            return

        # Convert messages to dict format
        message_dicts = []
        for msg in self._messages:
            message_dicts.append(
                {
                    "type": "human" if isinstance(msg, HumanMessage) else "ai",
                    "content": msg.content,
                    "timestamp": datetime.utcnow(),
                }
            )

        # Check if conversation exists
        doc = await self.async_collection.find_one({"_id": self.user_id})
        if not doc:
            # Create new conversation
            await self.async_collection.insert_one(
                {
                    "_id": self.user_id,
                    "summary": None,
                    "messages": message_dicts,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            )
        else:
            # Update existing conversation
            await self.async_collection.update_one(
                {"_id": self.user_id},
                {
                    "$set": {
                        "messages": message_dicts,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

    async def add_message_to_db(self, message: Union[HumanMessage, AIMessage]) -> None:
        """Add a single message to database"""
        doc = await self.async_collection.find_one({"_id": self.user_id})
        if not doc:
            await self.async_collection.insert_one(
                {
                    "_id": self.user_id,
                    "summary": None,
                    "messages": [],
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            )

        await self.async_collection.update_one(
            {"_id": self.user_id},
            {
                "$push": {
                    "messages": {
                        "type": "human" if isinstance(message, HumanMessage) else "ai",
                        "content": message.content,
                        "timestamp": datetime.utcnow(),
                    }
                }
            },
        )

    async def update_summary(self, summary: str):
        await self.async_collection.update_one(
            {"_id": self.user_id},
            {"$set": {"summary": summary, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    async def get_summary(self) -> str:
        doc = await self.async_collection.find_one({"_id": self.user_id})
        return doc.get("summary", "") if doc else ""

    async def clear_db(self):
        await self.async_collection.delete_one({"_id": self.user_id})
