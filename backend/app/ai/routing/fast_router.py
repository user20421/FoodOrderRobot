"""
轻量规则快速通道。

对于语义明确、可直接执行的高频意图，先走传统函数快速处理，避免调用大模型，
从而显著降低响应延迟。未命中快速通道的请求再进入 Handoff 多智能体图。
"""
from __future__ import annotations

import re
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.services import menu_service, order_service
from app.ai.graph.context import get_top_selling_dishes

logger = get_logger(__name__)


# 简单格式化 helper（与 chat_service 中快捷按钮保持一致风格）
def _format_top_dishes(dishes: List[Dict[str, Any]], title: str) -> str:
    if not dishes:
        return title + "\n本店有很多美味菜品，您可以看看菜单。"
    lines = [title]
    for i, dish in enumerate(dishes, 1):
        tags = dish.get("tags", "")
        short_desc = "·".join([t.strip() for t in tags.split(",") if t.strip()][:3]) if tags else ""
        if short_desc:
            lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）- {short_desc}")
        else:
            lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）")
    return "\n".join(lines)


async def _handle_confirm_order(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理下单/确认下单/结账类意图。"""
    if not re.search(r"(确认下单|我要下单|下单|结账|付款|提交订单)", message):
        return None
    if not cart:
        return {
            "response": "购物车为空，无法下单。请先添加菜品。",
            "cart": cart,
            "intent": "order",
            "agent": "order",
        }
    try:
        response = await order_service.create_order_from_cart(db, user_id, cart)
        return {
            "response": response,
            "cart": [],
            "intent": "order",
            "agent": "order",
        }
    except Exception as e:
        logger.warning(f"[FastRouter] 快捷确认下单失败，降级到 Agent: {e}")
        return None


async def _handle_view_menu(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理查看菜单类意图。"""
    if not re.search(r"(查看菜单|菜单|有什么菜|菜单一览|今天有什么)", message):
        return None
    top_dishes = await get_top_selling_dishes(db, 10) if db else []
    response = _format_top_dishes(top_dishes, "本店销量TOP10热门菜品：")
    response += "\n\n[点击浏览完整菜单](/menu)"
    return {
        "response": response,
        "cart": cart,
        "intent": "inquiry",
        "agent": "inquiry",
    }


async def _handle_recommend(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理推荐菜品类意图。"""
    if not re.search(r"(推荐|有什么好吃的|招牌菜|热销|热卖)", message):
        return None
    top_dishes = await get_top_selling_dishes(db, 5) if db else []
    response = _format_top_dishes(top_dishes, "为您推荐本店热销 TOP5 菜品：")
    return {
        "response": response,
        "cart": cart,
        "intent": "recommend",
        "agent": "recommend",
    }


async def _handle_query_orders(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理查询我的订单类意图。"""
    if not re.search(r"(查询我的订单|我的订单|订单记录|历史订单)", message):
        return None
    orders = await order_service.get_user_orders(db, user_id, 20) if db else []
    if orders:
        response = order_service.format_order_list(orders, title="您最近的订单如下：")
    else:
        response = "您还没有订单记录。"
    return {
        "response": response,
        "cart": cart,
        "intent": "service",
        "agent": "service",
    }


async def _handle_view_cart(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理查看购物车类意图（排除清空购物车）。"""
    if "清空" in message or not re.search(r"(看看购物车|查看购物车|购物车|cart)", message):
        return None
    if not cart:
        response = "当前购物车为空。"
    else:
        total = sum(float(c.get("unit_price", 0) or 0) * int(c.get("quantity", 1)) for c in cart)
        lines = [f"{c['name']} x{c['quantity']}" for c in cart]
        response = f"当前购物车：{'、'.join(lines)}\n合计：¥{total:.2f}"
    return {
        "response": response,
        "cart": cart,
        "intent": "order",
        "agent": "order",
    }


async def _handle_clear_cart(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理清空购物车类意图。"""
    if not re.search(r"(清空购物车|清空|全部删除)", message):
        return None
    return {
        "response": "购物车已清空。",
        "cart": [],
        "intent": "order",
        "agent": "order",
    }


# 快速通道处理器列表（按优先级排序）
_FAST_HANDLERS = [
    _handle_confirm_order,
    _handle_view_menu,
    _handle_recommend,
    _handle_query_orders,
    _handle_clear_cart,
    _handle_view_cart,
]


async def try_fast_path(
    message: str,
    cart: List[Dict[str, Any]],
    db: AsyncSession,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """
    尝试用规则快速通道处理用户消息。

    命中时返回 {"response": ..., "cart": ..., "intent": ..., "agent": ...}；
    未命中时返回 None，调用方应继续走 Handoff 多智能体图。
    """
    text = message.strip()
    if not text:
        return None

    for handler in _FAST_HANDLERS:
        try:
            result = await handler(text, cart, db, user_id)
            if result is not None:
                logger.info(f"[FastRouter] 命中快速通道: {handler.__name__}")
                return result
        except Exception as e:
            logger.warning(f"[FastRouter] {handler.__name__} 处理异常: {e}")
            continue

    return None
