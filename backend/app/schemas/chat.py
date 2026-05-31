"""
聊天相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    user_id: int
    message: str
    cart: Optional[List[dict]] = []


class ChatResponse(BaseModel):
    response: str
    cart: List[dict] = []
    intent: Optional[str] = None
    agent: Optional[str] = None


class ChatHistoryOut(BaseModel):
    id: int
    role: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
