"""
订单工具
提供购物车管理和订单创建能力
"""
from app.core.database import AsyncSessionLocal
from app.services.order_service import create_order
from app.repositories.order import get_orders_by_user, get_order_by_id


async def get_user_orders(user_id: int, limit: int = 10) -> list:
    """获取用户订单列表"""
    async with AsyncSessionLocal() as db:
        orders = await get_orders_by_user(db, user_id)
        return orders[:limit]


async def get_order_detail(order_id: int) -> dict | None:
    """获取订单详情"""
    async with AsyncSessionLocal() as db:
        order = await get_order_by_id(db, order_id)
        if not order:
            return None
        return {
            "id": order.id,
            "status": order.status,
            "total_price": order.total_price,
            "created_at": order.created_at,
            "items": [
                {
                    "name": oi.menu_item.name if oi.menu_item else f"菜品#{oi.menu_item_id}",
                    "quantity": oi.quantity,
                    "unit_price": oi.unit_price,
                    "subtotal": oi.unit_price * oi.quantity,
                }
                for oi in order.items
            ],
        }


async def get_latest_order(user_id: int) -> dict | None:
    """获取用户最新订单"""
    orders = await get_user_orders(user_id, limit=1)
    if not orders:
        return None
    return await get_order_detail(orders[0].id)


def merge_cart(existing_cart: list, new_items: list) -> list:
    """
    将新商品合并到现有购物车。
    同种商品数量累加。
    """
    cart_dict = {c["menu_item_id"]: c for c in existing_cart}
    for item in new_items:
        mid = item["menu_item_id"]
        if mid in cart_dict:
            cart_dict[mid]["quantity"] += item["quantity"]
        else:
            cart_dict[mid] = item.copy()
    return list(cart_dict.values())


def get_cart_summary(cart: list) -> str:
    """获取购物车摘要文本"""
    if not cart:
        return "购物车是空的"
    items_str = ", ".join([f"{c['name']}x{c['quantity']}" for c in cart])
    total = sum(c["unit_price"] * c["quantity"] for c in cart)
    return f"{items_str}，合计{total}元"


async def validate_cart_stock(cart: list) -> dict:
    """
    验证购物车中所有商品的库存是否充足。

    返回：{"valid": bool, "errors": [str], "insufficient": [{name, requested, available}]}
    """
    from app.ai.tools.menu_tools import get_all_menu_items

    errors = []
    insufficient = []
    items = await get_all_menu_items()
    item_map = {it.id: it for it in items}

    for c in cart:
        item = item_map.get(c["menu_item_id"])
        if not item:
            errors.append(f"商品 #{c['menu_item_id']} 不存在")
            continue
        if item.stock < c["quantity"]:
            errors.append(f"{item.name} 库存不足，仅剩 {item.stock} 份")
            insufficient.append({
                "name": item.name,
                "requested": c["quantity"],
                "available": item.stock,
            })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "insufficient": insufficient,
    }


async def submit_order(user_id: int, cart: list) -> dict:
    """
    提交订单。

    返回：{"success": bool, "order": Order|None, "error": str|None}
    """
    async with AsyncSessionLocal() as db:
        order = await create_order(db, user_id, cart)
        if isinstance(order, dict) and order.get("error"):
            return {"success": False, "order": None, "error": order["error"]}
        if order:
            return {"success": True, "order": order, "error": None}
        return {"success": False, "order": None, "error": "下单失败，请稍后重试"}


def format_order_list(orders: list) -> str:
    """格式化订单列表为文本"""
    if not orders:
        return "您当前还没有订单记录，来下一单吧～"

    lines = ["您的订单记录："]
    for o in orders:
        lines.append(
            f"订单号：{o.id} | 状态：{o.status} | 总价：{o.total_price}元 | "
            f"{o.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
    return "\n".join(lines)


def format_order_detail(order: dict) -> str:
    """格式化订单详情为文本"""
    if not order:
        return "订单不存在。"

    lines = [
        f"订单号：{order['id']}",
        f"状态：{order['status']}",
        f"下单时间：{order['created_at'].strftime('%Y-%m-%d %H:%M')}",
        f"总价：{order['total_price']}元",
        "\n菜品明细：",
    ]
    for item in order["items"]:
        lines.append(f"  {item['name']} x{item['quantity']} = {item['subtotal']}元")

    return "\n".join(lines)
