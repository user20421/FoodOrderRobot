"""
用户表 ORM
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(200), nullable=False, comment="密码bcrypt哈希")
    role = Column(String(20), default="customer", comment="角色: customer/admin")
    created_at = Column(DateTime, server_default=func.now())

    # 关系
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    chat_history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
