"""
文本格式化工具
"""
from datetime import datetime


def format_price(price: float) -> str:
    """格式化价格"""
    return f"{price:.2f}"


def format_datetime(dt: datetime) -> str:
    """格式化日期时间"""
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M")
    return ""


def order_status_text(status: str) -> str:
    """订单状态转中文"""
    mapping = {
        "pending": "待确认",
        "confirmed": "已确认",
        "completed": "已完成",
        "cancelled": "已取消",
    }
    return mapping.get(status, status)


def order_status_type(status: str) -> str:
    """订单状态转 Element UI tag type"""
    mapping = {
        "pending": "warning",
        "confirmed": "primary",
        "completed": "success",
        "cancelled": "info",
    }
    return mapping.get(status, "")


def cart_summary(cart: list) -> str:
    """购物车摘要"""
    if not cart:
        return "购物车为空"
    lines = []
    for item in cart:
        subtotal = item.get("unit_price", 0) * item.get("quantity", 1)
        lines.append(f"  {item['name']} x{item['quantity']} = {subtotal:.2f}元")
    return "\n".join(lines)


def export_order_text(order: dict) -> str:
    """导出订单为文本格式"""
    lines = [
        "=" * 40,
        "          本店订单详情",
        "=" * 40,
        f"订单号: {order.get('id', '')}",
        f"状态: {order_status_text(order.get('status', ''))}",
        f"下单时间: {format_datetime(order.get('created_at'))}",
        "-" * 40,
        "菜品明细:",
    ]
    for item in order.get("items", []):
        lines.append(f"  {item['name']} x{item['quantity']}  {item['unit_price']}元")
    lines.extend([
        "-" * 40,
        f"合计: {order.get('total_price', 0):.2f}元",
        "=" * 40,
        "感谢光临本店，期待再次为您服务！",
    ])
    return "\n".join(lines)
