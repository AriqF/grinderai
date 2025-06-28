from fastapi import HTTPException
from app.schemas.user_daily_progres_schema import UserTaskProgress
from app.schemas.user_schema import UserCreate
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from app.schemas.user_goals_schema import UserGoal, UserDailyTask, UserLongTermGoal
from datetime import datetime, timezone
import uuid
import json
from app.utils.util_func import get_current_time


class UserGoalService:
    def __init__(self, db: AsyncIOMotorDatabase, telegram_id: str):
        self.goal_collection = db["users_goals"]
        self.progress_collection = db["daily_progress"]
        self.telegram_id = telegram_id

    async def load_goals(self) -> Optional[dict]:
        try:
            doc_goals = await self.goal_collection.find_one({"_id": self.telegram_id})
            if not doc_goals:
                return None
            return UserGoal.model_validate(doc_goals)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def create_goals(self, goal: dict):
        try:
            now = get_current_time("Asia/Jakarta")
            daily_tasks = []
            if goal["daily_tasks"]:
                for task in goal["daily_tasks"]:
                    if task:
                        daily_tasks.append(
                            {
                                "id": task["id"],
                                "title": task["title"],
                                "note": task["note"],
                                "min_required_completion": task[
                                    "min_required_completion"
                                ],
                                "completion_unit": task["completion_unit"],
                                "created_at": now,
                                "updated_at": now,
                            }
                        )
            doc = await self.goal_collection.insert_one(
                {
                    "_id": self.telegram_id,
                    "long_term_goal": {
                        "summary": goal["long_term_goal"]["summary"],
                        "target_date": goal["long_term_goal"]["target_date"],
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                    },
                    "daily_tasks": daily_tasks,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            return doc
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def save_goals(self, goal: dict):
        try:
            doc = await self.goal_collection.find_one({"_id": self.telegram_id})
            if not doc:
                await self.create_goals(goal)
            else:
                await self.goal_collection.update_one(
                    {"_id": self.telegram_id},
                    {
                        "$set": {
                            "long_term_goal": goal["long_term_goal"],
                            "daily_tasks": goal["daily_tasks"],
                        },
                        "$setOnInsert": {"updated_at": datetime.utcnow()},
                    },
                    upsert=True,
                )
            return "OK"
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def add_daily_task(self, title: str, note: str, min_required_completion: int):
        now = get_current_time("Asia/Jakarta")
        task = {
            "id": str(uuid.uuid4()),
            "title": title,
            "note": note,
            "min_required_completion": min_required_completion,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self.goal_collection.update_one(
                {"_id": self.telegram_id},
                {"$push": {"daily_tasks": task}, "$set": {"updated_at": now}},
                upsert=True,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def update_daily_tasks(self, tasks: List[UserDailyTask]):
        now = get_current_time("Asia/Jakarta")
        try:
            await self.goal_collection.update_one(
                {"_id": self.telegram_id},
                {
                    "$set": {
                        "daily_tasks": [task.dict() for task in tasks],
                        "updated_at": now,
                    }
                },
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def delete_goals(self):
        try:
            await self.goal_collection.delete_one({"_id": self.telegram_id})
            return {"status": "deleted"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def save_complete_goal_to_db(self, goal_data: str) -> str:
        """Save complete goal with long-term goal and daily tasks to database"""
        try:
            data = json.loads(goal_data)

            # Create UserGoal object
            goal_id = str(uuid.uuid4())
            current_time = get_current_time("Asia/Jakarta")

            # Parse long-term goal
            long_term_data = data.get("long_term_goal", {})
            long_term_goal = UserLongTermGoal(
                summary=long_term_data.get("summary", ""),
                target_date=(
                    datetime.fromisoformat(long_term_data["target_date"])
                    if long_term_data.get("target_date")
                    else None
                ),
                status=long_term_data.get("status", "active"),
                created_at=current_time,
                updated_at=current_time,
            )

            # Parse daily tasks
            daily_tasks = []
            for task_data in data.get("daily_tasks", []):
                daily_task = UserDailyTask(
                    id=str(uuid.uuid4()),
                    title=task_data.get("title", ""),
                    note=task_data.get("note", ""),
                    min_required_completion=task_data.get("min_required_completion", 1),
                    created_at=current_time,
                    updated_at=current_time,
                )
                daily_tasks.append(daily_task)

            # Create complete UserGoal
            user_goal = UserGoal(
                id=goal_id,
                long_term_goal=long_term_goal,
                daily_tasks=daily_tasks,
                created_at=current_time,
                updated_at=current_time,
            )

            await self.goals_service.save_complete_goal(user_goal)
            return f"✅ Goal successfully saved! Long-term goal: '{long_term_goal.summary}' with {len(daily_tasks)} daily tasks."

        except Exception as e:
            return f"❌ Error saving goal: {str(e)}"

    async def llm_load_goals(self, dummy_input: str = "") -> str:
        """LLM to load goals from db"""
        try:
            goals = await self.load_goals()
            if not goals:
                return "No goals found. Ready to help you create your first long term goal!"

            result = "**Your currentt goals:**"
            for goal in goals:
                if goal["long_term_goal"]:
                    result += (
                        f"🎯 **Long-term Goal:** {goal["long_term_goal"]["summary"]}\n"
                    )
                    result += f"   Status: {goal["long_term_goal"]["status"]}\n"
                    if goal["long_term_goal"]["target_date"]:
                        result += f"   Target Date: {goal["long_term_goal"]["target_date"].strftime('%Y-%m-%d')}\n"
                if goal["daily_tasks"]:
                    result += f"   **Daily Tasks ({len(goal["daily_tasks"])}):**\n"
                    for task in goal["daily_tasks"]:
                        result += f"   • {task["title"]} (min: {task["min_required_completion"]}x)\n"
                        if task["note"]:
                            result += f"     Note: {task["note"]}\n"
                result += "\n"
            return result
        except Exception as e:
            return f"Error on retrieving goals {str(e)}"

    async def add_progress(self, progress: UserTaskProgress) -> bool:
        try:
            curr_date = get_current_time("Asia/Jakarta").strftime("%Y-%m-%d")
            existing_doc = await self.progress_collection.find_one(
                {
                    "telegram_id": self.telegram_id,
                    "date": curr_date,
                    "tasks.task_id": progress["task_id"],
                }
            )

            if not existing_doc:
                # Task doesn't exist, push it into the array
                result = await self.progress_collection.update_one(
                    {"telegram_id": self.telegram_id, "date": curr_date},
                    {"$push": {"tasks": progress}},
                )
                return result.modified_count > 0
            return False
        except Exception as e:
            raise e

    # TODO: add function to create a UserDailyProgress and Cron Job at 00:00 to update last progress and create today's progress
