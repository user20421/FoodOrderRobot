"""
订单业务服务
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import order as order_repo
from app.repositories import menu as menu_repo


async def create_order(db: AsyncSession, user_id: int, items: list[dict]):
    """
    创建订单
    items: list of {"menu_item_id": int, "quantity": int}
    返回订单对象，库存不足时返回错误信息字典
    """
    # 一次性查询所有需要的菜单项
    menu_item_ids = {item["menu_item_id"] for item in items}
    menu_items_map = {}
    for mid in menu_item_ids:
        menu_item = await menu_repo.get_menu_item_by_id(db, mid)
        if menu_item:
            menu_items_map[mid] = menu_item

    # 检查库存
    stock_errors = []
    for item in items:
        menu_item = menu_items_map.get(item["menu_item_id"])
        if not menu_item:
            stock_errors.append(f"菜品#{item['menu_item_id']} 不存在")
            continue
        quantity = item.get("quantity", 1)
        if menu_item.stock < quantity:
            stock_errors.append(f"{menu_item.name} 库存不足，仅剩 {menu_item.stock} 份")

    if stock_errors:
        return {"error": "、".join(stock_errors)}

    # 计算总价并扣减库存（在同一事务中）
    order_items_detail = []
    total_price = 0.0

    for item in items:
        menu_item = menu_items_map.get(item["menu_item_id"])
        if not menu_item:
            continue
        quantity = item.get("quantity", 1)
        unit_price = menu_item.price
        total_price += unit_price * quantity
        order_items_detail.append({
            "menu_item_id": menu_item.id,
            "quantity": quantity,
            "unit_price": unit_price,
        })
        # 扣减库存
        menu_item.stock -= quantity

    if not order_items_detail:
        return None

    # 创建订单（内部会 commit，且库存修改也在同一 session 中）
    order = await order_repo.create_order(db, user_id, order_items_detail, total_price)
    return order


async def get_order(db: AsyncSession, order_id: int):
    return await order_repo.get_order_by_id(db, order_id)
