from fastapi import HTTPException
from app.schemas.user_daily_progres_schema import UserTaskProgress
from app.schemas.user_schema import UserCreate
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from app.schemas.user_goals_schema import UserGoal, UserDailyTask, UserLongTermGoal
from app.schemas.user_daily_progres_schema import (
    UserDailyProgress,
    UserTaskProgress,
    UserTaskProgressExtended,
)
from datetime import datetime, timezone
import uuid
import json
from app.utils.util_func import get_current_time
import asyncio


class UserGoalService:
    def __init__(self, db: AsyncIOMotorDatabase, telegram_id: str):
        self.goal_collection = db["users_goals"]
        self.progress_collection = db["daily_progress"]
        self.telegram_id = telegram_id

    async def load_goals(self):
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

    async def load_daily_tasks_list(self):
        try:
            doc = await self.goal_collection.find_one({"_id": self.telegram_id})
            if not doc:
                return None
            dicted = UserGoal(**doc).model_dump()
            return dicted["daily_tasks"]
        except Exception as e:
            raise ValueError(e)

    async def create_user_daily_progress(self):
        try:
            now = get_current_time("Asia/Jakarta")
            curr_date = now.strftime("%Y-%m-%d")

            goals = await self.load_goals()
            if not goals:
                return None

            # create daily tasks
            if not goals.daily_tasks:
                return None

            # check duplicate for current date:
            find_dup = await self.progress_collection.find_one(
                {"date": curr_date, "telegram_id": self.telegram_id}
            )
            if find_dup:
                raise ValueError("DUPLICATE_ENTRY")

            tasks: List[UserTaskProgress] = []
            for task in goals.daily_tasks:
                tasks.append(
                    UserTaskProgress(
                        task_id=task.id,
                        title=task.title,
                        completed=False,
                        completed_at=None,
                        skip_reason=None,
                        obstacles=None,
                        notes=None,
                    )
                )

            data = UserDailyProgress(
                # _id=str(uuid.uuid4()),
                telegram_id=self.telegram_id,
                date=curr_date,
                tasks=tasks,
                overall_day_rating=None,
                mood_after_tasks=None,
                created_at=now,
                updated_at=now,
            )
            print(data.model_dump())
            await self.progress_collection.insert_one(data.model_dump())
            return "OK"
        except Exception as e:
            print(e)
            raise e

    async def load_progress_day_tasks(self):
        try:
            curr_date = curr_date = get_current_time("Asia/Jakarta").strftime(
                "%Y-%m-%d"
            )
            result = await self.progress_collection.find_one(
                {"telegram_id": self.telegram_id, "date": curr_date},
            )
            if not result:
                return None
            res_dict = UserDailyProgress(**result).model_dump()
            return [task for task in res_dict["tasks"]]
        except Exception as e:
            raise ValueError(e)

    async def convert_tasks_list_reminder(self):
        try:
            tasks_list, tasks_progress = await asyncio.gather(
                self.load_daily_tasks_list(), self.load_progress_day_tasks()
            )
            print(tasks_list)
            print(tasks_progress)
            if not tasks_list or not tasks_progress:
                raise ValueError("Tasks are empty")

            tasks_lookup = {item["id"]: item for item in tasks_list}

            extended: List[UserTaskProgressExtended] = []
            for progress in tasks_progress:
                task = tasks_lookup.get(progress["task_id"])
                extended.append(
                    UserTaskProgressExtended(
                        task_id=task["id"],
                        title=task["title"],
                        note=task["note"],
                        min_required_completion=task["min_required_completion"],
                        completion_unit=task["completion_unit"],
                        completed=progress["completed"],
                        completed_at=progress["completed_at"],
                    )
                )
            return [task.model_dump() for task in extended]
        except Exception as e:
            print(e)
            raise ValueError(e)

    async def update_daily_task(self, task_id: str, is_complete: bool):
        """Update daily task via Telegram callback.\n\nTODO: return doc and improve UI by displaying completed/skipped task name"""
        try:
            now = get_current_time("Asia/Jakarta")
            date = now.strftime("%Y-%m-%d")
            await self.progress_collection.update_one(
                {
                    "telegram_id": self.telegram_id,
                    "date": date,
                    "tasks.task_id": task_id,
                },
                {
                    "$set": {
                        "tasks.$.completed": is_complete,
                        "tasks.$.completed_at": now if is_complete else None,
                        "updated_at": now,
                    }
                },
            )
            return "OK"
        except Exception as e:
            raise ValueError(e)
