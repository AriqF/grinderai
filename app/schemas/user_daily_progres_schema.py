from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UserTaskProgress(BaseModel):
    task_id: str
    title: str
    completed: bool
    completed_at: Optional[datetime]
    notes: Optional[str]


class UserDailyProgress(BaseModel):
    telegram_id: str
    date: str
    tasks: Optional[List[UserTaskProgress]]
    created_at: datetime
    updated_at: datetime


class UserDailyProgressCreate(BaseModel):
    telegram_id: str
    date: str
    tasks: Optional[List[UserTaskProgress]]
    overall_day_rating: Optional[int]
    mood_after_tasks: Optional[str]


class UserTaskProgressExtended(BaseModel):
    task_id: str
    title: str
    note: str
    min_required_completion: int
    completion_unit: str
    completed: bool
    completed_at: Optional[bool]


class Config:
    arbitrary_types_allowed = True
    json_encoders = {datetime: lambda dt: dt.isoformat()}
