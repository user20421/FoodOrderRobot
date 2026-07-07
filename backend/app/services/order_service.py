"""
订单服务
负责订单创建、查询、格式化输出等业务逻辑，并统一控制数据库事务。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any, Tuple

from app.repositories.order_repo import order_repo, order_item_repo
from app.repositories.menu_repo import menu_item_repo
from app.schemas.order import OrderCreate, OrderOut, CartItem, OrderItemOut
from app.core.exceptions import BusinessException, NotFoundException
from app.core.logging_config import get_logger
from app.utils.formatters import order_status_text
from app.models.menu import MenuItem
from app.models.order import Order

logger = get_logger(__name__)


async def _resolve_cart_items(db: AsyncSession, cart: List[Dict[str, Any]]) -> Tuple[List[CartItem], List[str]]:
    """
    将前端/Agent 传来的购物车条目解析为结构化的 CartItem。
    如果缺少 menu_item_id，会按名称精确或模糊匹配菜单数据补充。
    无法识别的菜品会被跳过（并记录日志）。
    """
    if not cart:
        return [], []

    items: List[CartItem] = []
    skipped_names: List[str] = []

    for c in cart:
        menu_item_id = c.get("menu_item_id")
        name = c.get("name", "")

        # 如果缺少 menu_item_id，尝试通过名称查询数据库补充
        if not menu_item_id and name:
            menu_item = await menu_item_repo.get_by_name(db, name)
            # 精确匹配失败，尝试模糊匹配（数据库 LIKE，避免加载全表）
            if not menu_item:
                candidates = await menu_item_repo.search_by_keyword(db, name)
                # 取名称最相关的一条：优先名称包含查询词，再取第一条
                for mi in candidates:
                    if name in mi.name or mi.name in name:
                        menu_item = mi
                        break
                if not menu_item and candidates:
                    menu_item = candidates[0]
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
    注意：本函数不会修改传入的 cart，调用方需自行清空购物车。
    """
    if not cart:
        return "购物车为空，无法下单。请先添加菜品。"

    try:
        items, skipped_names = await _resolve_cart_items(db, cart)

        if not items:
            return "购物车中没有可识别的菜品，无法下单。请重新添加。"

        order = await create_order(db, user_id, items)
        msg = f"订单创建成功！订单号：{order.id}，总价：¥{order.total_price:.2f}。感谢您的订购！"
        if skipped_names:
            msg += f"（以下菜品无法识别已跳过：{', '.join(set(skipped_names))}）"
        return msg
    except Exception as e:
        logger.error(f"[OrderService] Agent 下单失败: {e}")
        return f"下单失败：{str(e)}，请稍后重试或联系服务员。"


async def cancel_order(db: AsyncSession, order_id: int, user_id: Optional[int] = None) -> bool:
    """
    取消指定订单。
    仅允许取消状态为 confirmed 的订单；若提供 user_id，则同时校验订单归属。
    事务由调用方控制，本函数不自行 commit。
    """
    order = await order_repo.get_with_items(db, order_id)
    if not order:
        raise NotFoundException(f"订单 #{order_id} 不存在")

    if user_id is not None and order.user_id != user_id:
        raise BusinessException("无权取消该订单")

    if order.status != "confirmed":
        raise BusinessException(f"订单 #{order_id} 当前状态为 {order.status}，无法取消")

    await order_repo.update_status(db, order_id, "cancelled")
    return True


async def get_user_orders(db: AsyncSession, user_id: int, limit: int = 20) -> List[OrderOut]:
    """获取用户订单"""
    orders = await order_repo.get_by_user(db, user_id, limit)
    return [_format_order(o) for o in orders]


async def get_user_orders_paginated(
    db: AsyncSession, user_id: int, page: int = 1, page_size: int = 10
) -> tuple[List[OrderOut], int]:
    """分页获取用户订单，返回 (订单列表, 总数)。"""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    skip = (page - 1) * page_size
    orders = await order_repo.get_by_user(db, user_id, limit=page_size, offset=skip)
    total = await order_repo.count_by_user(db, user_id)
    return [_format_order(o) for o in orders], total


async def count_user_orders(db: AsyncSession, user_id: int) -> int:
    return await order_repo.count_by_user(db, user_id)


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


async def get_all_orders_paginated(
    db: AsyncSession, page: int = 1, page_size: int = 10
) -> tuple[List[OrderOut], int]:
    """分页获取所有订单（商家），返回 (订单列表, 总数)。"""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    skip = (page - 1) * page_size
    orders = await order_repo.get_all_orders(db, skip, page_size)
    total = await order_repo.count_all(db)
    return [_format_order(o) for o in orders], total


async def count_all_orders(db: AsyncSession) -> int:
    return await order_repo.count_all(db)


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
    事务由调用方控制，本函数不自行 commit。
    """
    order = await order_repo.update_status(db, order_id, "completed")
    if not order:
        return None

    # 重新加载完整订单信息
    order = await order_repo.get_with_items(db, order_id)

    # 向用户聊天窗口推送完成通知
    try:
        from app.services.chat_service import notify_user_order_completed
        await notify_user_order_completed(order.user_id, order_id)
    except Exception as e:
        logger.warning(f"[OrderService] 订单完成通知发送失败: {e}")

    return _format_order(order)


def _item_name(it) -> str:
    """兼容 ORM OrderItem（带 menu_item 关联）和 OrderItemOut（直接有 name）。"""
    if hasattr(it, "menu_item"):
        return it.menu_item.name if it.menu_item else "未知菜品"
    return getattr(it, "name", "未知菜品")


def format_order_line(order) -> str:
    """单条订单格式化为文本行（供 Agent/Graph 使用）"""
    items_str = "，".join([
        f"{_item_name(it)} x{it.quantity}"
        for it in order.items
    ])
    time_str = order.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(order.created_at, "strftime") else str(order.created_at)
    return f"订单号：{order.id}，状态：{order_status_text(order.status)}，总价：¥{order.total_price:.2f}，菜品：{items_str}，下单时间：{time_str}"


def format_order_list(orders, title: str = "您最近的订单如下：", total: int = 0) -> str:
    """订单列表格式化（供 Agent/Graph 使用）。
    仅展示前 5 条，若总数超过 5 条则附上看全部订单的链接。
    """
    lines = [title]
    for idx, o in enumerate(orders[:5], 1):
        lines.append(f"{idx}. {format_order_line(o)}")
    if total > 5:
        lines.append(f"\n共 {total} 条订单，[查看全部订单](/orders)")
    return "\n".join(lines)


async def format_user_orders(db: AsyncSession, user_id: int, limit: int = 5) -> str:
    """查询用户最近订单并以文本形式返回（供 Agent 使用），最多展示 5 条。"""
    try:
        total = await order_repo.count_by_user(db, user_id)
        orders = await order_repo.get_by_user(db, user_id, limit)
        if not orders:
            return "您还没有订单记录。"
        return format_order_list(orders, title="您最近的订单如下：", total=total)
    except Exception as e:
        logger.error(f"[OrderService] 查询用户订单失败: {e}")
        return f"查询订单失败：{str(e)}"


async def get_min_max_orders_in_range(
    db: AsyncSession, user_id: int, days: int = 15, min_count: int = 1, max_count: int = 1
) -> str:
    """
    查询用户最近 N 天内总价最高/最低的若干笔订单。
    返回格式化的文本结果，供 Agent 直接展示。
    """
    from datetime import datetime, timedelta
    try:
        end = datetime.now()
        start = end - timedelta(days=max(1, days))
        orders = await order_repo.get_by_user_in_date_range(db, user_id, start, end)
        if not orders:
            return f"最近 {days} 天内您没有订单记录。"
        if len(orders) == 1:
            return f"最近 {days} 天内您只有一笔订单：\n{format_order_line(orders[0])}"

        min_count = max(1, min_count)
        max_count = max(1, max_count)
        sorted_by_price = sorted(orders, key=lambda o: o.total_price)
        min_orders = sorted_by_price[:min_count]
        max_orders = sorted_by_price[-max_count:][::-1]

        lines = [f"最近 {days} 天内您共有 {len(orders)} 笔订单。", ""]

        if max_count == 1:
            lines.append(f"数额最大：{format_order_line(max_orders[0])}")
        else:
            lines.append(f"数额最大的 {len(max_orders)} 笔订单：")
            for idx, o in enumerate(max_orders, 1):
                lines.append(f"{idx}. {format_order_line(o)}")

        lines.append("")

        if min_count == 1:
            lines.append(f"数额最小：{format_order_line(min_orders[0])}")
        else:
            lines.append(f"数额最小的 {len(min_orders)} 笔订单：")
            for idx, o in enumerate(min_orders, 1):
                lines.append(f"{idx}. {format_order_line(o)}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[OrderService] 查询最大/最小订单失败: {e}")
        return f"查询失败：{str(e)}"


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
