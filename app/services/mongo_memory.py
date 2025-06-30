from typing import List, Union
from datetime import datetime
from langchain.schema import BaseChatMessageHistory, HumanMessage, AIMessage
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException
import pymongo
from app.utils.util_func import get_current_time
from datetime import datetime
import pytz


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

    # Alternative version using MongoDB aggregation for better performance
    async def load_conversations_by_date(
        self, date: str
    ) -> List[Union[AIMessage, HumanMessage]]:
        """
        Load messages using MongoDB aggregation for better performance
        """
        try:
            # Parse the input date and localize to Jakarta timezone
            jakarta = pytz.timezone("Asia/Jakarta")
            start_local = jakarta.localize(datetime.strptime(date, "%Y-%m-%d"))
            end_local = jakarta.localize(
                datetime.strptime(date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            )

            # Convert to UTC for MongoDB comparison
            start_utc = start_local.astimezone(pytz.utc)
            end_utc = end_local.astimezone(pytz.utc)

            print(f"Querying messages between {start_utc} and {end_utc}")

            # Use aggregation to filter messages at database level
            pipeline = [
                {"$match": {"_id": self.user_id}},
                {"$unwind": "$messages"},
                {
                    "$match": {
                        "messages.timestamp": {"$gte": start_utc, "$lte": end_utc}
                    }
                },
                {"$sort": {"messages.timestamp": 1}},  # Sort by timestamp
                {"$project": {"message": "$messages"}},
            ]

            cursor = self.async_collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)

            messages = []
            for result in results:
                m = result["message"]
                if m["type"] == "human":
                    messages.append(HumanMessage(content=m["content"]))
                elif m["type"] == "ai":
                    messages.append(AIMessage(content=m["content"]))

            print(f"Found {len(messages)} messages for date {date}")
            return messages

        except Exception as e:
            print(f"Error in load_conversations_by_date_optimized: {e}")
            return []

    async def save_messages_to_db(self) -> None:
        """Save current messages to database"""
        now = get_current_time("Asia/Jakarta")
        if not self._messages:
            return

        # Convert messages to dict format
        message_dicts = []
        for msg in self._messages:
            message_dicts.append(
                {
                    "type": "human" if isinstance(msg, HumanMessage) else "ai",
                    "content": msg.content,
                    "timestamp": now,
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
                    "created_at": now,
                    "updated_at": now,
                }
            )
        else:
            # Update existing conversation
            await self.async_collection.update_one(
                {"_id": self.user_id},
                {
                    "$set": {
                        "messages": message_dicts,
                        "updated_at": now,
                    }
                },
            )

    async def add_message_to_db(self, message: Union[HumanMessage, AIMessage]) -> None:
        """Add a single message to database"""
        now = get_current_time("Asia/Jakarta")
        print(now)
        doc = await self.async_collection.find_one({"_id": self.user_id})
        if not doc:
            await self.async_collection.insert_one(
                {
                    "_id": self.user_id,
                    "summary": None,
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                }
            )

        await self.async_collection.update_one(
            {"_id": self.user_id},
            {
                "$push": {
                    "messages": {
                        "type": "human" if isinstance(message, HumanMessage) else "ai",
                        "content": message.content,
                        "timestamp": now,
                    }
                }
            },
        )

    async def update_summary(self, summary: str):
        await self.async_collection.update_one(
            {"_id": self.user_id},
            {
                "$set": {
                    "summary": summary,
                    "updated_at": get_current_time("Asia/Jakarta"),
                }
            },
            upsert=True,
        )

    async def get_summary(self) -> str:
        doc = await self.async_collection.find_one({"_id": self.user_id})
        return doc.get("summary", "") if doc else ""

    async def clear_db(self):
        await self.async_collection.delete_one({"_id": self.user_id})

    def format_history_for_prompt(
        self,
        messages: List[Union[AIMessage, HumanMessage]],
    ) -> str:
        """Convert message history to a safe string format for prompts"""
        if not messages:
            return "No previous conversation history."

        formatted_history = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                # Escape curly braces and format safely
                content = msg.content.replace("{", "{{").replace("}", "}}")
                formatted_history.append(f"User: {content}")
            elif isinstance(msg, AIMessage):
                content = msg.content.replace("{", "{{").replace("}", "}}")
                formatted_history.append(f"Rune: {content}")

        return "\n".join(formatted_history)
