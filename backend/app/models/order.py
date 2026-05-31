"""
订单模型
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, func, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    status = Column(String(20), default="confirmed", comment="状态: pending/confirmed/completed/cancelled")
    total_price = Column(Float, nullable=False, default=0, comment="总价")
    remark = Column(Text, nullable=True, comment="订单备注")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, comment="订单ID")
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False, comment="菜品ID")
    quantity = Column(Integer, default=1, nullable=False, comment="数量")
    unit_price = Column(Float, nullable=False, comment="单价")
    created_at = Column(DateTime, server_default=func.now())

    # 关联
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")
