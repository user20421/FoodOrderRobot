"""
菜单相关工具 Mixin。
"""
from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.services import menu_service

logger = get_logger(__name__)


class MenuToolsMixin:
    """菜单工具的共享实现（需配合 ToolContext 使用）。"""

    db_session: Any

    def _require_db(self):
        ...  # 由 ToolContext 实现

    async def get_menu(self, limit: int = 40) -> str:
        """获取完整菜单（默认展示前 limit 条，避免提示词过长）。"""
        self._require_db()
        try:
            menu = await menu_service.get_full_menu(self.db_session)
            items = menu.get("items", [])
            if not items:
                return "菜单暂时没有菜品。"
            lines = [f"{item.name} ¥{item.price:.0f}（{item.category}）" for item in items[:limit]]
            return "菜单：\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"[Tool] get_menu 失败: {e}")
            return f"获取菜单失败：{str(e)}"

    async def search_dishes(self, query: str) -> str:
        """按关键词搜索菜品。"""
        self._require_db()
        try:
            items = await menu_service.search_menu_items(self.db_session, query)
            if not items:
                return f"没有找到与「{query}」相关的菜品。"
            lines = [f"{item.name} ¥{item.price:.0f} - {item.description or '无描述'}" for item in items[:10]]
            return "搜索结果：\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"[Tool] search_dishes 失败: {e}")
            return f"搜索失败：{str(e)}"

    async def get_dish_info(self, dish_name: str) -> str:
        """获取指定菜品详情。"""
        self._require_db()
        try:
            item = await menu_service.get_item_by_name(self.db_session, dish_name)
            if not item:
                return f"菜单中没有「{dish_name}」。"
            return (
                f"{item.name} ¥{item.price:.0f}\n"
                f"分类：{item.category}\n"
                f"描述：{item.description or '暂无'}\n"
                f"辣度：{item.spicy_level}\n"
                f"库存：{item.stock if item.stock is not None else '充足'}\n"
                f"标签：{item.tags or '无'}"
            )
        except Exception as e:
            logger.error(f"[Tool] get_dish_info 失败: {e}")
            return f"查询失败：{str(e)}"

    async def check_stock(self, dish_name: str) -> str:
        """查询菜品库存。"""
        self._require_db()
        try:
            item = await menu_service.get_item_by_name(self.db_session, dish_name)
            if not item:
                return f"菜单中没有「{dish_name}」。"
            return f"{item.name} 当前库存：{item.stock if item.stock is not None else '充足'}"
        except Exception as e:
            logger.error(f"[Tool] check_stock 失败: {e}")
            return f"查询库存失败：{str(e)}"

    async def get_recommended_dishes(self, preference: str = "", limit: int = 5) -> str:
        """获取推荐菜品；无明确偏好时按推荐标签->销量 fallback。"""
        self._require_db()
        try:
            if preference:
                items = await menu_service.search_menu_items(self.db_session, preference)
            else:
                items = await menu_service.get_recommended_items(self.db_session, limit)
                if not items:
                    items = await menu_service.get_top_selling_items(self.db_session, limit)
            items = items[:limit] if items else []
            if not items:
                return "暂时没有可推荐的菜品。"
            lines = [f"{item.name} ¥{item.price:.0f} - {item.description or '热门推荐'}" for item in items]
            return "推荐菜品：\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"[Tool] get_recommended_dishes 失败: {e}")
            return f"推荐失败：{str(e)}"
