from fastapi import APIRouter, Depends, HTTPException
from app.schemas.user_schema import UserCreate, UserOut
from app.db.mongo import get_database
from app.services.user_service import UserService
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.util_func import get_current_time
from app.schemas.user_daily_progres_schema import UserDailyProgressCreate
from app.services.goals_service import UserGoalService

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
