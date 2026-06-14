"""
订单服务
负责订单创建、查询、格式化输出等业务逻辑，并统一控制数据库事务。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any

from app.repositories.order_repo import order_repo, order_item_repo
from app.repositories.menu_repo import menu_item_repo
from app.schemas.order import OrderCreate, OrderOut, CartItem, OrderItemOut
from app.core.exceptions import BusinessException, NotFoundException
from app.core.logging_config import get_logger
from app.utils.formatters import order_status_text
from app.models.menu import MenuItem
from app.models.order import Order

logger = get_logger(__name__)


async def _resolve_cart_items(db: AsyncSession, cart: List[Dict[str, Any]]) -> List[CartItem]:
    """
    将前端/Agent 传来的购物车条目解析为结构化的 CartItem。
    如果缺少 menu_item_id，会按名称精确或模糊匹配菜单数据补充。
    无法识别的菜品会被跳过（并记录日志）。
    """
    if not cart:
        return []

    # 预加载所有菜单项用于模糊匹配
    all_menu_result = await db.execute(select(MenuItem))
    all_menu_items = list(all_menu_result.scalars().all())

    items: List[CartItem] = []
    skipped_names: List[str] = []

    for c in cart:
        menu_item_id = c.get("menu_item_id")
        name = c.get("name", "")

        # 如果缺少 menu_item_id，尝试通过名称查询数据库补充
        if not menu_item_id and name:
            menu_item = await menu_item_repo.get_by_name(db, name)
            # 精确匹配失败，尝试模糊匹配
            if not menu_item:
                for mi in all_menu_items:
                    if name in mi.name or mi.name in name:
                        menu_item = mi
                        break
            if menu_item:
                menu_item_id = menu_item.id
                name = menu_item.name
            else:
                skipped_names.append(name)
                logger.warning(f"[OrderService] 购物车菜品无法识别: {name}")
                continue

        if not menu_item_id:
            skipped_names.append(name or "未知菜品")
            continue

        items.append(CartItem(
            menu_item_id=int(menu_item_id),
            name=name or "未知菜品",
            quantity=max(1, int(c.get("quantity", 1))),
            unit_price=float(c.get("unit_price", 0) or 0),
        ))

    return items, skipped_names


async def _create_order_in_transaction(db: AsyncSession, user_id: int, items: List[CartItem], remark: str = None) -> Order:
    """
    创建订单的核心实现（不管理事务边界，调用方必须已在事务中）。
    流程：校验库存 -> 创建订单 -> 创建订单项 -> 原子扣减库存 -> 增加销量。
    """
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

    # 创建订单项并扣减库存/增加销量
    for oi_data in order_items_data:
        oi_data["order_id"] = order.id
        await order_item_repo.create(db, oi_data)

        # 原子扣减库存：返回 0 表示库存不足
        affected = await menu_item_repo.update_stock(db, oi_data["menu_item_id"], -oi_data["quantity"])
        if affected == 0:
            raise BusinessException(f"'{menu_item.name}' 库存不足，下单失败")

        await menu_item_repo.increment_sales(db, oi_data["menu_item_id"], oi_data["quantity"])

    return order


async def create_order(db: AsyncSession, user_id: int, items: List[CartItem], remark: str = None) -> OrderOut:
    """
    创建订单。
    整个流程在同一个事务中完成：校验库存 -> 创建订单 -> 创建订单项 -> 原子扣减库存 -> 增加销量。
    如果调用方已经开启了事务，则复用该事务且不自行 commit；否则在本函数内显式 commit。
    """
    if not items:
        raise BusinessException("购物车不能为空")

    reuse_tx = db.in_transaction()
    order = await _create_order_in_transaction(db, user_id, items, remark)
    if not reuse_tx:
        await db.commit()

    # 重新加载带 items 的订单（事务已提交或复用外部事务，均可安全加载关联）
    order = await order_repo.get_with_items(db, order.id)
    return _format_order(order)


async def create_order_from_cart(db: AsyncSession, user_id: int, cart: List[Dict[str, Any]]) -> str:
    """
    供 Agent 调用的便捷方法：根据购物车创建订单并返回可读的文本结果。
    """
    if not cart:
        return "购物车为空，无法下单。请先添加菜品。"

    try:
        items, skipped_names = await _resolve_cart_items(db, cart)

        if not items:
            return "购物车中没有可识别的菜品，无法下单。请重新添加。"

        order = await create_order(db, user_id, items)
        cart.clear()
        msg = f"订单创建成功！订单号：{order.id}，总价：¥{order.total_price:.2f}。感谢您的订购！"
        if skipped_names:
            msg += f"（以下菜品无法识别已跳过：{', '.join(set(skipped_names))}）"
        return msg
    except Exception as e:
        logger.error(f"[OrderService] Agent 下单失败: {e}")
        return f"下单失败：{str(e)}，请稍后重试或联系服务员。"


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


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """获取商家仪表盘统计数据。"""
    today_orders = await order_repo.get_today_orders(db)
    today_revenue = sum(o.total_price for o in today_orders)
    pending_count = await order_repo.count_pending_orders(db)
    return {
        "today_orders": len(today_orders),
        "today_revenue": today_revenue,
        "pending_orders": pending_count,
    }


async def get_pending_orders(db: AsyncSession, limit: int = 100) -> List[OrderOut]:
    """获取待处理订单（未完成的订单）。"""
    orders = await order_repo.get_pending_orders(db, limit)
    return [_format_order(o) for o in orders]


async def complete_order(db: AsyncSession, order_id: int) -> Optional[OrderOut]:
    """
    商家完成订单制作。
    1. 更新订单状态为 completed
    2. 向用户聊天记录推送一条完成通知
    """
    order = await order_repo.update_status(db, order_id, "completed")
    if not order:
        return None

    await db.commit()

    # 重新加载完整订单信息
    order = await order_repo.get_with_items(db, order_id)

    # 向用户聊天窗口推送完成通知
    try:
        from app.services.chat_service import notify_user_order_completed
        await notify_user_order_completed(order.user_id, order_id)
    except Exception as e:
        logger.warning(f"[OrderService] 订单完成通知发送失败: {e}")

    return _format_order(order)


def format_order_line(order) -> str:
    """单条订单格式化为文本行（供 Agent/Graph 使用）"""
    items_str = "，".join([
        f"{(it.menu_item.name if it.menu_item else '未知菜品')} x{it.quantity}"
        for it in order.items
    ])
    time_str = order.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(order.created_at, "strftime") else str(order.created_at)
    return f"订单号：{order.id}，状态：{order_status_text(order.status)}，总价：¥{order.total_price:.2f}，菜品：{items_str}，下单时间：{time_str}"


def format_order_list(orders, title: str = "您最近的订单如下：") -> str:
    """订单列表格式化（供 Agent/Graph 使用）"""
    lines = [title]
    for idx, o in enumerate(orders, 1):
        lines.append(f"{idx}. {format_order_line(o)}")
    return "\n".join(lines)


async def format_user_orders(db: AsyncSession, user_id: int, limit: int = 20) -> str:
    """查询用户订单并以文本形式返回（供 Agent 使用）"""
    try:
        orders = await order_repo.get_by_user(db, user_id, limit)
        if not orders:
            return "您还没有订单记录。"
        return format_order_list(orders, title="您最近的订单如下：")
    except Exception as e:
        logger.error(f"[OrderService] 查询用户订单失败: {e}")
        return f"查询订单失败：{str(e)}"


async def format_order_detail(db: AsyncSession, order_id: int) -> str:
    """查询订单详情并以文本形式返回（供 Agent 使用）"""
    try:
        order = await order_repo.get_with_items(db, order_id)
        if not order:
            return f"订单 #{order_id} 不存在。"
        return f"订单详情：{format_order_line(order)}"
    except Exception as e:
        logger.error(f"[OrderService] 查询订单详情失败: {e}")
        return f"查询订单详情失败：{str(e)}"


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
