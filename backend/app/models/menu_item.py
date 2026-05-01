"""
菜品表 ORM
"""
from sqlalchemy import Column, Integer, String, Float, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="菜品名称")
    description = Column(Text, comment="菜品描述")
    price = Column(Float, nullable=False, comment="价格")
    spicy_level = Column(Integer, default=0, comment="辣度 0-5")
    category = Column(String(50), comment="分类")
    tags = Column(String(200), comment="标签，逗号分隔")
    stock = Column(Integer, default=100, comment="库存数量")

    order_items = relationship("OrderItem", back_populates="menu_item")
