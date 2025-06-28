from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MessageConversation(BaseModel):
    type: str
    content: str
    timestamp: datetime


class ConversationCreate(BaseModel):
    summary: str
    messages: List[MessageConversation]


class Conversation(BaseModel):
    _id: str
    summary: str
    messages: List[MessageConversation]
    created_at: datetime
    updated_at: datetime


class Config:
    arbitrary_types_allowed = True
    json_encoders = {datetime: lambda dt: dt.isoformat()}
