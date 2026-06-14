"""
聊天记录 Beanie Document
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import Field
from beanie import Document


class ChatMessageDocument(Document):
    """聊天记录文档"""
    user_id: int
    session_id: str = "default"
    role: str
    message: str
    cart_snapshot: Optional[List[Dict[str, Any]]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "chat_messages"
        indexes = [
            [("user_id", 1), ("session_id", 1), ("created_at", 1)],
        ]
