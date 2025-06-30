from fastapi import APIRouter, Depends, HTTPException
from app.schemas.user_schema import UserCreate, UserOut
from app.db.mongo import get_database
from app.services.user_service import UserService
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.util_func import get_current_time
from fastapi.encoders import jsonable_encoder

router = APIRouter()


@router.get("/time")
def get_time():
    return get_current_time("Asia/Jakarta").strftime("%Y-%m-%d")


@router.post("/", response_model=UserOut)
async def create_user(
    user: UserCreate, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        repo = UserService(db)
        existing = await repo.get_user_by_id(user.telegram_id)
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")
        new_user = await repo.create_user(user)
        return new_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{telegram_id}", response_model=UserOut)
async def get_user(telegram_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        repo = UserService(db)
        user = await repo.get_user_by_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{telegram_id}/goals")
async def update_goals(
    telegram_id: str, goals: list[str], db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        service = UserService(db)
        success = await service.update_goals(telegram_id, goals)
        if not success:
            raise HTTPException(
                status_code=404, detail="User not found or update failed"
            )
        return {"message": "Goals updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("level/inc")
async def inc_exp(
    telegram_id: str, amount: int, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        service = UserService(db)
        update = await service.increase_exp(str(telegram_id), int(amount))
        return jsonable_encoder(update)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("level/dec")
async def inc_exp(
    telegram_id: str, amount: int, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        service = UserService(db)
        update = await service.decrease_exp(str(telegram_id), int(amount))
        return jsonable_encoder(update)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
