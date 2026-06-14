"""
对话摘要 Beanie Document
"""
from datetime import datetime, timezone
from pydantic import Field
from beanie import Document


class ConversationSummaryDocument(Document):
    """对话摘要文档"""
    user_id: int
    session_id: str = "default"
    summary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "conversation_summaries"
        indexes = [
            [("user_id", 1), ("session_id", 1)],
        ]
