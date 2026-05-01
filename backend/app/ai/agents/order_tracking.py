"""
订单追踪智能体 (OrderTrackingAgent)

职责：查询用户的历史订单记录和订单详情。
"""
import re

from app.ai.agents.base import BaseAgent
from app.ai.tools import (
    get_user_orders,
    get_order_detail,
    get_latest_order,
    format_order_list,
    format_order_detail,
)


class OrderTrackingAgent(BaseAgent):
    """
    订单追踪智能体
    负责查询和展示用户的订单历史，不处理任何下单或购物车操作。
    """

    def __init__(self):
        super().__init__(
            name="订单追踪专员",
            description="查询用户订单历史、订单详情和订单状态",
        )

    async def run(self, user_id: int, message: str, cart: list = None) -> dict:
        msg = message.lower()

        # 判断是否要查最新订单详情
        if any(k in msg for k in ["最新", "最近", "上一个", "刚才", "最后"]):
            order = await get_latest_order(user_id)
            if not order:
                return {"response": "您当前还没有订单记录，来下一单吧～"}
            detail_text = format_order_detail(order)
            return {"response": f"您最新的订单详情：\n{detail_text}"}

        # 判断是否要查某个具体订单号
        order_id_match = re.search(r"(\d+)", message)
        if order_id_match and any(k in msg for k in ["号", "订单", "详情"]):
            order_id = int(order_id_match.group(1))
            order = await get_order_detail(order_id)
            if not order:
                return {"response": f"未找到订单号 {order_id} 的订单。"}
            detail_text = format_order_detail(order)
            return {"response": f"订单 {order_id} 详情：\n{detail_text}"}

        # 默认：返回订单列表
        orders = await get_user_orders(user_id, limit=10)
        return {"response": format_order_list(orders)}
