from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UserDailyMood(BaseModel):
    telegram_id: str
    date: str
    summary: str
    mood_label: List[str]
    mood_polarity: str
    motivation_level: str
    energy_level: str
    task_completed: Optional[int]
    task_skipped: Optional[int]
    created_at: datetime
    updated_at: datetime


class UserDailyMoodPrediction(BaseModel):
    summary: str
    mood_label: List[str]
    mood_polarity: str
    motivation_level: str
    energy_level: str
