"""
菜单模型
"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, comment="分类名称")
    sort_order = Column(Integer, default=0, comment="排序")
    description = Column(Text, nullable=True, comment="分类描述")
    created_at = Column(DateTime, server_default=func.now())


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="菜品名称")
    description = Column(Text, nullable=True, comment="菜品描述")
    # 金额使用 Float 方便迁移；生产环境建议改为 Numeric(10,2)
    price = Column(Float, nullable=False, comment="价格（元）")
    spicy_level = Column(Integer, default=0, comment="辣度 0-5")
    category = Column(String(50), nullable=False, comment="分类名称")
    tags = Column(String(300), nullable=True, comment="标签，逗号分隔")
    stock = Column(Integer, default=100, comment="库存数量")
    is_recommended = Column(Integer, default=0, comment="是否推荐 0/1")
    sales_count = Column(Integer, default=0, comment="销量")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    order_items = relationship("OrderItem", back_populates="menu_item")

    # 常用查询索引
    __table_args__ = (
        Index("idx_menu_item_name", "name"),
        Index("idx_menu_item_category", "category"),
        Index("idx_menu_item_sales", "sales_count"),
    )
