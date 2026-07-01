"""
购物车相关工具 Mixin。
"""
from __future__ import annotations

from typing import Any, Dict

from app.core.logging_config import get_logger
from app.services import menu_service

logger = get_logger(__name__)


class CartToolsMixin:
    """购物车工具的共享实现（需配合 ToolContext 使用）。"""

    db_session: Any
    user_id: Any
    cart: list

    def _require_db(self):
        ...  # 由 ToolContext 实现

    def _find_cart_item(self, dish_name: str) -> Dict[str, Any] | None:
        ...  # 由 ToolContext 实现

    def _format_cart(self) -> str:
        ...  # 由 ToolContext 实现

    async def add_to_cart(self, dish_name: str, quantity: int = 1) -> str:
        """将菜品添加到购物车；若已存在则累加数量。"""
        self._require_db()
        try:
            item = await menu_service.get_item_by_name(self.db_session, dish_name)
            if not item:
                return f"抱歉，菜单中没有找到「{dish_name}」，请确认菜名。"
            existing = next((i for i in self.cart if i.get("name") == item.name), None)
            qty = max(1, quantity)
            if existing:
                existing["quantity"] += qty
                existing["unit_price"] = float(item.price)
            else:
                self.cart.append({
                    "name": item.name,
                    "quantity": qty,
                    "unit_price": float(item.price),
                    "menu_item_id": item.id,
                })
            return f"已添加 {item.name} x{qty} 到购物车，当前购物车：{self._format_cart()}"
        except Exception as e:
            logger.error(f"[Tool] add_to_cart 失败: {e}")
            return f"添加失败：{str(e)}"

    async def update_cart_quantity(self, dish_name: str, quantity: int) -> str:
        """修改购物车中菜品的数量；quantity=0 表示移除。"""
        existing = self._find_cart_item(dish_name)
        if not existing:
            return f"购物车中没有「{dish_name}」。"
        if quantity <= 0:
            self.cart.remove(existing)
            return f"已将 {existing['name']} 从购物车移除。当前购物车：{self._format_cart()}"
        existing["quantity"] = quantity
        return f"已将 {existing['name']} 数量改为 {quantity}。当前购物车：{self._format_cart()}"

    async def remove_from_cart(self, dish_name: str) -> str:
        """从购物车中移除指定菜品。"""
        existing = self._find_cart_item(dish_name)
        if not existing:
            return f"购物车中没有「{dish_name}」。"
        self.cart.remove(existing)
        return f"已将 {existing['name']} 从购物车移除。当前购物车：{self._format_cart()}"

    async def view_cart(self) -> str:
        """查看当前购物车。"""
        return f"当前购物车：{self._format_cart()}"

    async def clear_cart(self) -> str:
        """清空购物车。"""
        self.cart.clear()
        return "购物车已清空。"
