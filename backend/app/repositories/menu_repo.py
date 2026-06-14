"""
菜单数据访问层
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional

from app.models.menu import MenuCategory, MenuItem
from app.repositories.base import BaseRepository


class MenuCategoryRepository(BaseRepository[MenuCategory]):
    def __init__(self):
        super().__init__(MenuCategory)

    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[MenuCategory]:
        result = await db.execute(select(MenuCategory).where(MenuCategory.name == name))
        return result.scalar_one_or_none()

    async def get_all_ordered(self, db: AsyncSession) -> List[MenuCategory]:
        result = await db.execute(select(MenuCategory).order_by(MenuCategory.sort_order))
        return result.scalars().all()


class MenuItemRepository(BaseRepository[MenuItem]):
    def __init__(self):
        super().__init__(MenuItem)

    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[MenuItem]:
        result = await db.execute(select(MenuItem).where(MenuItem.name == name))
        return result.scalar_one_or_none()

    async def get_by_category(self, db: AsyncSession, category: str) -> List[MenuItem]:
        result = await db.execute(
            select(MenuItem).where(MenuItem.category == category).order_by(MenuItem.id)
        )
        return result.scalars().all()

    async def get_recommended(self, db: AsyncSession, limit: int = 8) -> List[MenuItem]:
        result = await db.execute(
            select(MenuItem)
            .where(MenuItem.is_recommended == 1)
            .order_by(MenuItem.sales_count.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def search_by_keyword(self, db: AsyncSession, keyword: str) -> List[MenuItem]:
        result = await db.execute(
            select(MenuItem).where(
                (MenuItem.name.contains(keyword)) |
                (MenuItem.tags.contains(keyword)) |
                (MenuItem.description.contains(keyword))
            )
        )
        return result.scalars().all()

    async def update_stock(self, db: AsyncSession, item_id: int, delta: int) -> int:
        """
        原子更新库存。delta 为负数时表示扣减。
        返回受影响的行数；若返回 0，说明库存不足或菜品不存在。
        """
        result = await db.execute(
            update(MenuItem)
            .where(MenuItem.id == item_id)
            .where(MenuItem.stock + delta >= 0)
            .values(stock=MenuItem.stock + delta)
        )
        return result.rowcount

    async def increment_sales(self, db: AsyncSession, item_id: int, quantity: int) -> int:
        """增加销量，返回受影响的行数"""
        result = await db.execute(
            update(MenuItem)
            .where(MenuItem.id == item_id)
            .values(sales_count=MenuItem.sales_count + quantity)
        )
        return result.rowcount


menu_category_repo = MenuCategoryRepository()
menu_item_repo = MenuItemRepository()
