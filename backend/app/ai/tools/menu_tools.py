"""
菜单相关工具
"""
from typing import List, Optional
from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal
from app.repositories.menu_repo import menu_item_repo
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@tool
def get_menu() -> str:
    """获取完整菜单列表"""
    return "请调用API获取完整菜单数据。"


@tool
def search_dishes(query: str) -> str:
    """
    按关键词搜索菜品
    Args:
        query: 搜索关键词（如'辣的'、'鸡肉'、'清淡'）
    """
    return f"搜索菜品: {query}"


@tool
def get_dish_info(dish_name: str) -> str:
    """
    获取指定菜品的详细信息（价格、描述、辣度、库存等）
    Args:
        dish_name: 菜品名称
    """
    return f"查询菜品: {dish_name}"


@tool
def check_stock(dish_name: str) -> str:
    """
    查询菜品的库存状态
    Args:
        dish_name: 菜品名称
    """
    return f"查询库存: {dish_name}"


@tool
def get_recommended_dishes(preference: str = None, limit: int = 5) -> str:
    """
    获取推荐菜品
    Args:
        preference: 偏好描述（如'不辣'、'海鲜'、'下饭菜'）
        limit: 推荐数量
    """
    return f"推荐菜品: 偏好={preference}, 数量={limit}"
