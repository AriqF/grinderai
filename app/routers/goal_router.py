from fastapi import APIRouter, Depends, HTTPException
from app.schemas.user_schema import UserCreate, UserOut
from app.db.mongo import get_database
from app.services.user_service import UserService
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.util_func import get_current_time
from app.schemas.user_daily_progres_schema import UserDailyProgressCreate
from app.services.goals_service import UserGoalService
from app.utils.bot_handler import bot
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.services.scheduler_service import SchedulerService
from app.services.llm_service import LLMService

router = APIRouter()


@router.post("/create-progress")
async def create_progress(
    telegram_id: str, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        goal_service = UserGoalService(db, telegram_id)
        return await goal_service.create_user_daily_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/day-tasks")
async def find_today_tasks(
    telegram_id: str, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        goal_service = UserGoalService(db, telegram_id)
        user_service = UserService(db)

        tasks, user = await asyncio.gather(
            goal_service.convert_tasks_list_reminder(),
            user_service.get_user_by_id(telegram_id),
        )
        first_message = (
            f"👋 *Hi there {user["first_name"]}!*\n\n"
            "Here are your daily tasks. Please confirm your progress by selecting the appropriate action below each task.\n\n"
            "_Note: These messages won’t appear in chat history once completed or skipped._"
        )
        await bot.send_message(
            chat_id=int(telegram_id), text=first_message, parse_mode="Markdown"
        )
        # Send each task with 0.5s delay
        for i, task in enumerate(tasks, 1):
            message = (
                f"*📝 Task {i}:* {task['title']}\n"
                f"🗒️ _{task['note']}_\n"
                f"🔢 *Minimum required:* {task['min_required_completion']} {task['completion_unit']}"
            )

            if not task["completed"]:
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ Complete",
                                callback_data=f"complete:{task['task_id']}",
                            ),
                            InlineKeyboardButton(
                                "⏭ Skip", callback_data=f"skip:{task['task_id']}"
                            ),
                        ]
                    ]
                )
            else:
                keyboard = None
            await bot.send_message(
                chat_id=int(telegram_id),
                text=message,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            await asyncio.sleep(0.5)

        return "OK"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/scheduler")
async def test_scheduler(db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        scheduler_service = SchedulerService(db)
        return await scheduler_service.remind_daily_tasks()
    except Exception as e:
        ValueError(e)


@router.post("/test-daily-share")
async def test_daily_share(
    telegram_id: str, name: str, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        service = LLMService(db, telegram_id)
        return await service.ask_daily_sharing(name)
    except Exception as e:
        ValueError(e)


@router.get("/test-mood-analyzer")
async def test_mood_analyzer(
    telegram_id: str, name: str, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        service = LLMService(db, telegram_id)
        result = await service.insert_mood_summary(name)
        return result
    except Exception as e:
        ValueError(e)
