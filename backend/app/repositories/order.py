"""
订单数据访问层
"""
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_item import OrderItem


async def create_order(db: AsyncSession, user_id: int, items: list[dict], total_price: float):
    """
    创建订单及订单项
    items: list of {"menu_item_id": int, "quantity": int, "unit_price": float}
    """
    order = Order(user_id=user_id, total_price=total_price, status="confirmed")
    db.add(order)
    await db.flush()  # 获取 order.id

    for item in items:
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=item["menu_item_id"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
        )
        db.add(order_item)

    await db.commit()

    # 重新加载订单及其关联项，避免异步懒加载问题
    result = await db.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return result.scalar_one()


async def get_order_by_id(db: AsyncSession, order_id: int):
    result = await db.execute(
        select(Order).where(Order.id == order_id).options(
            selectinload(Order.items).selectinload(OrderItem.menu_item)
        )
    )
    return result.scalar_one_or_none()


async def get_orders_by_user(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Order).where(Order.user_id == user_id).options(
            selectinload(Order.items).selectinload(OrderItem.menu_item)
        )
    )
    return result.scalars().all()
