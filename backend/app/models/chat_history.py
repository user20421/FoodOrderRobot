"""
聊天历史表 ORM
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False, comment="user / assistant")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="chat_history")
