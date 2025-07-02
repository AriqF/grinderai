from langchain.tools import tool
from app.services.goals_service import UserGoalService
from app.db.mongo import get_database


@tool
async def save_goal_to_db(user_id: str, goal: dict) -> str:
    """Save the user's long-term goal to the database."""
    db = await get_database()
    goal_service = UserGoalService(db, user_id)
    await goal_service.save_goals(goal)
    return "Goals have been saved!"


@tool
async def get_current_goal(user_id: str) -> str:
    """Get the user's current long-term and daily goal."""
    db = await get_database()
    goal_service = UserGoalService(db, user_id)
    return await goal_service.load_goals()
