"""
用户画像 Beanie Document
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import Field
from beanie import Document


class UserProfileDocument(Document):
    """用户画像文档"""
    user_id: int
    profile: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "user_profiles"
        indexes = [
            [("user_id", 1)],
        ]
