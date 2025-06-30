from app.utils.util_func import get_current_time
from app.db.mongo import get_database
from app.services.goals_service import UserGoalService
from app.services.user_service import UserService
from app.services.scheduler_service import SchedulerService


def test_cron_job():
    print("🔁 Running scheduled task..")


async def remind_user_tasks():
    try:
        db = await get_database()
        scheduler_service = SchedulerService(db)
        await scheduler_service.remind_daily_tasks()
        return "OK"
    except Exception as e:
        print("REMIND_USER_TASKS ERR ", e)
        raise ValueError(e)


async def daily_progress_creation():
    try:
        db = await get_database()
        scheduler_service = SchedulerService(db)
        await scheduler_service.daily_progress_creation()
        return "OK"
    except Exception as e:
        print("REMIND_USER_TASKS ERR ", e)
        raise ValueError(e)


async def ask_daily_share():
    try:
        db = await get_database()
        scheduler_service = SchedulerService(db)
        await scheduler_service.ask_daily_share()
        return "OK"
    except Exception as e:
        print("REMIND_USER_TASKS ERR ", e)
        raise ValueError(e)
