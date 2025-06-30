from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UserCreate(BaseModel):
    telegram_id: str
    first_name: str
    last_name: Optional[str]
    username: str
    language: str


class UserOut(BaseModel):
    id: str = Field(..., alias="_id")
    telegram_id: str
    username: str
    level: Optional[int] = 1
    exp: Optional[int] = 0
    created_at: datetime
    updated_at: Optional[datetime]


class UserBasicInfo(BaseModel):
    telegram_id: str
    first_name: str
    last_name: Optional[str]
    username: str
    language: str


class Config:
    validate_by_name = True
    json_encoders = {datetime: lambda dt: dt.isoformat()}
