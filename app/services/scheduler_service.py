from motor.motor_asyncio import AsyncIOMotorDatabase
from app.schemas.user_schema import UserBasicInfo
from typing import List
from app.services.goals_service import UserGoalService
from app.services.user_service import UserService
from app.utils.bot_handler import bot
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
from app.services.llm_service import LLMService
from app.utils.util_func import get_current_time
from datetime import datetime, timedelta


class SchedulerService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        # self.goal_collection = db["users_goals"]
        # self.progress_collection = db["daily_progress"]
        self.user_collection = db["users"]

    async def remind_daily_tasks(self):
        try:
            user_service = UserService(self.db)
            user_list = await user_service.find_all()

            for user in user_list:
                tg_id = str(user["telegram_id"])
                print("USER ON PROCESS ", tg_id)
                user_goal_service = UserGoalService(self.db, tg_id)
                tasks = await user_goal_service.convert_tasks_list_reminder()
                first_message = (
                    f"👋 *Hi there {user["first_name"]}!*\n\n"
                    "Here are your daily tasks. Please confirm your progress by selecting the appropriate action below each task.\n\n"
                    "_Note: These reminder won’t appear in Rune chat history_"
                )
                await bot.send_message(
                    chat_id=int(tg_id),
                    text=first_message,
                    parse_mode="Markdown",
                )
                # Send each task with 0.5s delay
                for i, task in enumerate(tasks, 1):
                    if not task["completed"]:
                        keyboard = InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        "✅ Complete",
                                        callback_data=f"complete:{task['task_id']}",
                                    ),
                                    InlineKeyboardButton(
                                        "⏭ Skip",
                                        callback_data=f"skip:{task['task_id']}",
                                    ),
                                ]
                            ]
                        )
                        message = (
                            f"*📝 Task {i}:* {task['title']}\n"
                            f"🗒️ _{task['note']}_\n"
                            f"🔢 *Minimum required:* {task['min_required_completion']} {task['completion_unit']}"
                        )
                    else:
                        message = (
                            f"*📝 Task {i}:* {task['title']}\n"
                            f"🗒️ _{task['note']}_\n"
                            f"🔢 *Minimum required:* {task['min_required_completion']} {task['completion_unit']}"
                            f"✅ _Task Already Completed_"
                        )
                        keyboard = None
                    await bot.send_message(
                        chat_id=int(user["telegram_id"]),
                        text=message,
                        reply_markup=keyboard,
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(0.5)
        except Exception as e:
            print("REMIND_ERR ", e)
            raise ValueError(e)

    async def daily_progress_creation(self):
        try:
            user_service = UserService(self.db)
            user_list = await user_service.find_all()
            for user in user_list:
                tg_id = str(user["telegram_id"])
                goal_service = UserGoalService(self.db, tg_id)
                await goal_service.create_user_daily_progress()
            return "OK"
        except Exception as e:
            print("DAILY_PROGRESS_CREATION ERR", e)
            raise ValueError(e)

    async def ask_daily_share(self):
        try:
            user_service = UserService(self.db)
            user_list = await user_service.find_all()
            for user in user_list:
                llm_service = LLMService(self.db, str(user["telegram_id"]))
                text = await llm_service.ask_daily_sharing(user["first_name"])
                await bot.send_message(
                    chat_id=int(user["telegram_id"]),
                    text=text,
                    parse_mode="Markdown",
                )
            return "OK"
        except Exception as e:
            print("ASK_DAILY_SHARE_SCHED_ERR", e)
            raise ValueError(e)

    async def analyze_daily_sentiment(self):
        try:
            user_service = UserService(self.db)
            user_list = await user_service.find_all()
            for user in user_list:
                llm_service = LLMService(self.db, str(user["telegram_id"]))
                yesterday = get_current_time("Asia/Jakarta") - timedelta(days=1)
                result = await llm_service.get_mood_sentiment(
                    user["first_name"], yesterday
                )
            return "OK"
        except Exception as e:
            raise ValueError(e)
