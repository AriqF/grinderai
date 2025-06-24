from fastapi import APIRouter, Depends, HTTPException
from app.schemas.user_schema import UserCreate, UserOut
from app.db.mongo import get_database
from app.repositories.user_repo import UserRepository
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter()


@router.post("/", response_model=UserOut)
async def create_user(
    user: UserCreate, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        repo = UserRepository(db)
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
        repo = UserRepository(db)
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
        repo = UserRepository(db)
        success = await repo.update_goals(telegram_id, goals)
        if not success:
            raise HTTPException(
                status_code=404, detail="User not found or update failed"
            )
        return {"message": "Goals updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
