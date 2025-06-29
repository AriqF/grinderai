from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UserTaskProgress(BaseModel):
    task_id: str
    title: str
    completed: bool
    completed_at: Optional[bool]
    skip_reason: Optional[str]
    obstacles: Optional[List[str]]
    notes: Optional[str]


class UserDailyProgress(BaseModel):
    id: str = Field(..., alias="_id")
    telegram_id: str
    date: str
    tasks: Optional[List[UserTaskProgress]]
    overall_day_rating: Optional[int]
    mood_after_tasks: Optional[str]
    created_at: datetime
    updated_at: datetime


class UserDailyProgressCreate(BaseModel):
    telegram_id: str
    date: str
    tasks: Optional[List[UserTaskProgress]]
    overall_day_rating: Optional[int]
    mood_after_tasks: Optional[str]


class Config:
    arbitrary_types_allowed = True
    json_encoders = {datetime: lambda dt: dt.isoformat()}
