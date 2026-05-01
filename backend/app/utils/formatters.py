"""
格式化工具
提供订单、菜单等数据的文本格式化功能
"""


def format_order_to_txt(order) -> str:
    """将单个订单格式化为 TXT 文本"""
    lines = [
        "=" * 50,
        f"订单号：{order.id}",
        f"用户ID：{order.user_id}",
        f"状态：{order.status}",
        f"下单时间：{order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else '-'}",
        f"总价：{order.total_price} 元",
        "-" * 50,
        "菜品明细：",
    ]
    for oi in order.items:
        name = oi.menu_item.name if oi.menu_item else f"菜品#{oi.menu_item_id}"
        subtotal = oi.unit_price * oi.quantity
        lines.append(f"  {name}  x{oi.quantity}  单价：{oi.unit_price}元  小计：{subtotal}元")
    lines.append("=" * 50)
    return "\n".join(lines)


def format_orders_to_txt(orders: list, title: str = "订单列表") -> str:
    """将多个订单格式化为 TXT 文本"""
    if not orders:
        return "暂无订单记录。"
    lines = [
        "=" * 60,
        f"  {title}",
        f"  共 {len(orders)} 笔订单",
        "=" * 60,
        "",
    ]
    for order in orders:
        lines.append(format_order_to_txt(order))
        lines.append("")
    return "\n".join(lines)
