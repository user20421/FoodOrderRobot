"""
ORM 模型注册
显式导入所有模型，确保 Base.metadata 包含所有表
"""
from app.models.user import User
from app.models.menu import MenuCategory, MenuItem
from app.models.order import Order, OrderItem
from app.models.chat import ChatHistory

__all__ = ["User", "MenuCategory", "MenuItem", "Order", "OrderItem", "ChatHistory"]
