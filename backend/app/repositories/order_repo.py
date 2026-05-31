"""
订单数据访问层
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.models.order import Order, OrderItem
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self):
        super().__init__(Order)

    async def get_by_user(self, db: AsyncSession, user_id: int, limit: int = 20) -> List[Order]:
        result = await db.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(desc(Order.created_at))
            .limit(limit)
            .options(selectinload(Order.items).selectinload(OrderItem.menu_item))
        )
        return result.scalars().all()

    async def get_with_items(self, db: AsyncSession, order_id: int) -> Optional[Order]:
        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).selectinload(OrderItem.menu_item))
        )
        return result.scalar_one_or_none()

    async def get_all_orders(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Order]:
        result = await db.execute(
            select(Order)
            .order_by(desc(Order.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(Order.items).selectinload(OrderItem.menu_item))
        )
        return result.scalars().all()


class OrderItemRepository(BaseRepository[OrderItem]):
    def __init__(self):
        super().__init__(OrderItem)


order_repo = OrderRepository()
order_item_repo = OrderItemRepository()
