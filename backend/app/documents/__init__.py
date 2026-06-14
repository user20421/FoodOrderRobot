"""
MongoDB Beanie Document 模型
用于替代原始 Motor 查询，提供 Pydantic 类型安全的异步 ODM
"""
from app.documents.chat import ChatMessageDocument
from app.documents.profile import UserProfileDocument
from app.documents.summary import ConversationSummaryDocument

__all__ = [
    "ChatMessageDocument",
    "UserProfileDocument",
    "ConversationSummaryDocument",
]
