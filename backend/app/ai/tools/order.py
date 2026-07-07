"""
订单相关工具 Mixin。
"""
from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.services import order_service

logger = get_logger(__name__)


class OrderToolsMixin:
    """订单工具的共享实现（需配合 ToolContext 使用）。"""

    db_session: Any
    user_id: Any
    cart: list

    def _require_db(self):
        ...  # 由 ToolContext 实现

    async def confirm_order(self) -> str:
        """确认下单：将购物车提交为订单，扣减库存并清空购物车。"""
        self._require_db()
        if not self.cart:
            return "购物车为空，无法下单。"
        try:
            result = await order_service.create_order_from_cart(
                self.db_session, self.user_id, self.cart
            )
            if "成功" in result:
                self.cart.clear()
            return result
        except Exception as e:
            logger.error(f"[Tool] confirm_order 失败: {e}")
            return f"下单失败：{str(e)}"

    async def get_my_orders(self, limit: int = 20) -> str:
        """查询当前用户的订单历史。"""
        self._require_db()
        try:
            return await order_service.format_user_orders(self.db_session, self.user_id, limit)
        except Exception as e:
            logger.error(f"[Tool] get_my_orders 失败: {e}")
            return f"查询订单失败：{str(e)}"

    async def get_order_detail(self, order_id: int) -> str:
        """查询指定订单详情。"""
        self._require_db()
        try:
            return await order_service.format_order_detail(self.db_session, order_id)
        except Exception as e:
            logger.error(f"[Tool] get_order_detail 失败: {e}")
            return f"查询订单详情失败：{str(e)}"

    async def cancel_order(self, order_id: int) -> str:
        """取消指定订单。"""
        self._require_db()
        try:
            await order_service.cancel_order(self.db_session, order_id, self.user_id)
            return f"订单 #{order_id} 已取消。"
        except Exception as e:
            logger.error(f"[Tool] cancel_order 失败: {e}")
            return f"取消订单失败：{str(e)}"

    async def get_min_max_orders(
        self, days: int = 15, min_count: int = 1, max_count: int = 1
    ) -> str:
        """
        查询最近 N 天内总价最高/最低的若干笔订单。
        例如用户问"最近10天总价最小的3份订单和总价最高的1份订单"时，使用 days=10, min_count=3, max_count=1。
        """
        self._require_db()
        try:
            return await order_service.get_min_max_orders_in_range(
                self.db_session, self.user_id, days, min_count, max_count
            )
        except Exception as e:
            logger.error(f"[Tool] get_min_max_orders 失败: {e}")
            return f"查询失败：{str(e)}"
