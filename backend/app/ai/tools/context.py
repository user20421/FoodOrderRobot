"""
Agent 工具运行时上下文。

保存单次 LLM 调用期间的共享状态（购物车、数据库会话、用户信息），
并通过 Mixin 组合购物车/菜单/订单/店铺等具体工具方法。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.tools.cart import CartToolsMixin
from app.ai.tools.menu import MenuToolsMixin
from app.ai.tools.order import OrderToolsMixin
from app.ai.tools.store import StoreToolsMixin


class ToolContext(CartToolsMixin, MenuToolsMixin, OrderToolsMixin, StoreToolsMixin):
    """单次 LLM 调用期间的工具有状态上下文。"""

    def __init__(
        self,
        state: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ):
        self.state = state
        self.config = config or {}
        self.db_session = self.config.get("configurable", {}).get("db_session")
        self.user_id = state.get("user_id")
        self.cart: List[Dict[str, Any]] = list(state.get("cart") or [])
        self.tool_outputs: List[str] = []

    def _require_db(self):
        if not self.db_session:
            raise RuntimeError("工具需要数据库会话，但 config['configurable']['db_session'] 未注入")

    def _find_cart_item(self, dish_name: str) -> Optional[Dict[str, Any]]:
        """按名称（子串互含）在购物车中查找条目。"""
        for item in self.cart:
            item_name = item.get("name") or ""
            if dish_name in item_name or item_name in dish_name:
                return item
        return None

    def _format_cart(self) -> str:
        """将购物车格式化为简短文本。"""
        if not self.cart:
            return "购物车为空"
        lines = [f"{i['name']} x{i['quantity']}" for i in self.cart]
        return "、".join(lines)

    def get_state_update(self) -> Dict[str, Any]:
        """返回对 AgentState 的更新（主要是购物车）。"""
        return {"cart": self.cart}
