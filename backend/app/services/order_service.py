"""
订单服务
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.repositories.order_repo import order_repo, order_item_repo
from app.repositories.menu_repo import menu_item_repo
from app.schemas.order import OrderCreate, OrderOut, CartItem, OrderItemOut
from app.core.exceptions import BusinessException, NotFoundException


async def create_order(db: AsyncSession, user_id: int, items: List[CartItem], remark: str = None) -> OrderOut:
    """创建订单"""
    if not items:
        raise BusinessException("购物车不能为空")

    total_price = 0.0
    order_items_data = []

    # 验证库存并计算总价
    for item in items:
        menu_item = await menu_item_repo.get(db, item.menu_item_id)
        if not menu_item:
            raise NotFoundException(f"菜品不存在: {item.name}")
        if menu_item.stock < item.quantity:
            raise BusinessException(f"'{menu_item.name}' 库存不足，仅剩 {menu_item.stock} 份")

        total_price += menu_item.price * item.quantity
        order_items_data.append({
            "menu_item_id": item.menu_item_id,
            "quantity": item.quantity,
            "unit_price": menu_item.price,
        })

    # 创建订单
    order = await order_repo.create(db, {
        "user_id": user_id,
        "status": "confirmed",
        "total_price": total_price,
        "remark": remark,
    })

    # 创建订单项并扣减库存
    for oi_data in order_items_data:
        oi_data["order_id"] = order.id
        await order_item_repo.create(db, oi_data)
        await menu_item_repo.update_stock(db, oi_data["menu_item_id"], -oi_data["quantity"])
        await menu_item_repo.increment_sales(db, oi_data["menu_item_id"], oi_data["quantity"])

    # 重新加载带items的订单
    order = await order_repo.get_with_items(db, order.id)
    return _format_order(order)


async def get_user_orders(db: AsyncSession, user_id: int, limit: int = 20) -> List[OrderOut]:
    """获取用户订单"""
    orders = await order_repo.get_by_user(db, user_id, limit)
    return [_format_order(o) for o in orders]


async def get_order_detail(db: AsyncSession, order_id: int) -> Optional[OrderOut]:
    """获取订单详情"""
    order = await order_repo.get_with_items(db, order_id)
    if not order:
        return None
    return _format_order(order)


async def get_all_orders(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[OrderOut]:
    """获取所有订单（商家）"""
    orders = await order_repo.get_all_orders(db, skip, limit)
    return [_format_order(o) for o in orders]


def _format_order(order) -> OrderOut:
    """格式化订单输出"""
    items = []
    for oi in order.items:
        items.append(OrderItemOut(
            id=oi.id,
            menu_item_id=oi.menu_item_id,
            name=oi.menu_item.name if oi.menu_item else "未知菜品",
            quantity=oi.quantity,
            unit_price=oi.unit_price,
            subtotal=oi.quantity * oi.unit_price,
        ))
    return OrderOut(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        total_price=order.total_price,
        remark=order.remark,
        items=items,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
