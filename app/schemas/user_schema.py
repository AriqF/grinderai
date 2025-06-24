from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UserCreate(BaseModel):
    telegram_id: str
    username: str
    long_term_goals: Optional[List[str]] = []


class UserOut(BaseModel):
    id: str = Field(..., alias="_id")
    telegram_id: str
    username: str
    long_term_goals: List[str]
    current_level: Optional[int] = 1
    exp_points: Optional[int] = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}
