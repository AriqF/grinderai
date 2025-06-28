from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UserLongTermGoal(BaseModel):
    summary: str
    target_date: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime


class UserDailyTask(BaseModel):
    id: str
    title: str
    note: str
    min_required_completion: int
    completion_unit: str
    created_at: datetime
    updated_at: datetime


class UserGoal(BaseModel):
    id: str = Field(..., alias="_id")
    long_term_goal: Optional[UserLongTermGoal] = None
    daily_tasks: Optional[List[UserDailyTask]] = []
    created_at: datetime
    updated_at: datetime


class Config:
    allow_population_by_field_name = True
    json_encoders = {datetime: lambda v: v.isoformat()}
