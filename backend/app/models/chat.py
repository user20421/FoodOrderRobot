"""
聊天记录模型（MySQL fallback）
主要聊天记录存储在 MongoDB，此表作为降级备份
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    session_id = Column(String(50), default="default", comment="会话ID")
    role = Column(String(20), nullable=False, comment="角色: user/assistant/system")
    message = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联
    user = relationship("User", back_populates="chat_history")
