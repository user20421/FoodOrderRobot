"""
订单相关工具
"""
from langchain_core.tools import tool


@tool
def confirm_order() -> str:
    """
    确认下单
    将购物车中的菜品提交为正式订单，扣减库存，清空购物车
    必须在用户明确同意后才能调用
    """
    return "confirm_order"


@tool
def get_my_orders(limit: int = 10) -> str:
    """
    查询当前用户的全部订单历史（会返回最近20条订单，包含每条订单的详细信息）
    当用户问"我的订单""查看订单""所有订单""订单记录"时，必须调用此工具
    Args:
        limit: 不需要指定，系统会自动返回足够的订单
    """
    return f"查询订单历史: 最近{limit}条"


@tool
def get_order_detail(order_id: int) -> str:
    """
    查询某个特定订单号的详细内容（仅当用户明确提供了订单号时才调用）
    如果用户问"我的订单""查看所有订单"，不要调用此工具，应调用 get_my_orders
    Args:
        order_id: 订单ID
    """
    return f"查询订单详情: {order_id}"


@tool
def cancel_order(order_id: int) -> str:
    """
    取消指定订单
    Args:
        order_id: 订单ID
    """
    return f"取消订单: {order_id}"
