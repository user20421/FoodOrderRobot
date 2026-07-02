"""
轻量规则快速通道。

对于语义明确、可直接执行的高频意图，先走传统函数快速处理，避免调用大模型，
从而显著降低响应延迟。未命中快速通道的请求再进入 LLM 分类器或多智能体图。
"""
from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.content_loader import get_menu_items, get_faq_data, get_store_docs
from app.services import menu_service, order_service
from app.ai.graph.context import get_top_selling_dishes

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 格式化 helper
# ---------------------------------------------------------------------------

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


def _format_cart(cart: List[Dict[str, Any]]) -> str:
    if not cart:
        return "当前购物车为空。"
    total = sum(float(c.get("unit_price", 0) or 0) * int(c.get("quantity", 1)) for c in cart)
    lines = [f"{c['name']} x{c['quantity']}" for c in cart]
    return f"当前购物车：{'、'.join(lines)}\n合计：¥{total:.2f}"


# ---------------------------------------------------------------------------
# 菜单名称缓存（用于快速加购时的精确匹配）
# ---------------------------------------------------------------------------

_MENU_ITEM_NAMES: Optional[List[str]] = None


def _get_menu_item_names() -> List[str]:
    """从 Markdown 菜单加载菜品名称列表，按长度降序排列以避免短名覆盖长名。"""
    global _MENU_ITEM_NAMES
    if _MENU_ITEM_NAMES is None:
        _MENU_ITEM_NAMES = sorted(
            [item["name"] for item in get_menu_items()],
            key=len,
            reverse=True,
        )
    return _MENU_ITEM_NAMES


# ---------------------------------------------------------------------------
# 知识库快速匹配
# ---------------------------------------------------------------------------

_FAQ_KEYWORDS: Optional[Dict[str, str]] = None
_STORE_KEYWORDS: Optional[Dict[str, str]] = None


def _load_faq_keywords() -> Dict[str, str]:
    """加载 FAQ 关键词映射（问题 -> 答案）"""
    global _FAQ_KEYWORDS
    if _FAQ_KEYWORDS is None:
        _FAQ_KEYWORDS = {}
        for faq in get_faq_data():
            q = faq["question"]
            _FAQ_KEYWORDS[q] = faq["answer"]
    return _FAQ_KEYWORDS


def _load_store_keywords() -> Dict[str, str]:
    """加载店铺文档关键词映射（标题 -> 正文）"""
    global _STORE_KEYWORDS
    if _STORE_KEYWORDS is None:
        _STORE_KEYWORDS = {}
        for doc in get_store_docs():
            title = doc["title"]
            _STORE_KEYWORDS[title] = doc["content"]
    return _STORE_KEYWORDS


# ---------------------------------------------------------------------------
# 意图辅助函数
# ---------------------------------------------------------------------------

_ORDER_VERBS = r"来|上|要|加|给我|我要|(?<!几)点|点一份|来一份|来两份|来三份"
_SERVICE_KEYWORDS = r"营业|配送|会员|优惠|电话|地址|预订|预约|订单|投诉|建议|时间|多久|怎么|做法|是什么|几点|发票|打包|外卖|堂食|座位|包厢|停车|WiFi|无线|网络|折扣|活动|满减|优惠券|代金券|积分|充值|余额|退款|取消|开票"
# 明确的续点/追加信号，用于在没有报出具体菜名时仍能识别出点餐意图
_STRONG_ORDER_SIGNALS = r"加菜|再点|还要点|再要|再加点|追加|再来一份|还要一份|上一份|点一个|来一份"


def _has_mixed_intent(message: str) -> bool:
    """
    判断消息是否同时包含下单意图和服务/咨询意图。
    混合意图消息应交由 Agent 统一处理，避免快速通道只回答一半。

    为了避免误判，这里要求"下单意图"必须是真实的：
    - 消息中明确包含"数量/量词 + 菜品名"，或
    - 包含"加菜/再点/追加"等强点餐信号。
    单纯的语气词（吗/？/可以/能不能）不再被视为服务意图。
    """
    has_service = bool(re.search(_SERVICE_KEYWORDS, message))
    if not has_service:
        return False

    has_order = bool(re.search(_STRONG_ORDER_SIGNALS, message)) or len(_extract_dish_orders(message)) > 0
    return has_order


_CN_NUMBERS = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _parse_quantity(qty_str: Optional[str]) -> int:
    """解析阿拉伯数字或中文数字数量"""
    if not qty_str:
        return 1
    qty_str = qty_str.strip()
    if qty_str.isdigit():
        return max(1, int(qty_str))
    # 简单中文数字，如"两"、"二"、"三"
    total = 0
    for ch in qty_str:
        if ch in _CN_NUMBERS:
            total += _CN_NUMBERS[ch]
    return max(1, total) if total > 0 else 1


def _extract_dish_orders(message: str) -> List[Tuple[str, int]]:
    """
    从消息中提取所有菜品及数量。
    仅处理纯点餐消息（调用方已排除混合意图）。
    """
    names = _get_menu_item_names()
    if not names:
        return []

    names_pattern = "|".join(re.escape(n) for n in names)
    qty_pattern = r"[一二两三四五六七八九十\d]+"
    unit_pattern = r"(?:份|个|碗|盘|杯|份儿|个儿)"

    # 模式A：动词+可选数量/量词+菜品
    # 如"来一份麻婆豆腐"、"来碗白米饭"、"给我点一份宫保鸡丁"、"我要毛血旺"
    pattern_a = re.compile(
        rf"(?:({_ORDER_VERBS})\s*({qty_pattern})?\s*{unit_pattern}?|"
        rf"({qty_pattern})\s*{unit_pattern})\s*({names_pattern})"
    )

    # 模式B：菜品+数量/量词，如"麻婆豆腐来一份"、"毛血旺两份"
    pattern_b = re.compile(
        rf"({names_pattern})\s*(?:({_ORDER_VERBS})?\s*({qty_pattern})?\s*{unit_pattern})"
    )

    results: List[Tuple[str, int]] = []
    seen: set = set()

    for match in pattern_a.finditer(message):
        verb, qty_str1, qty_str2, name = match.group(1), match.group(2), match.group(3), match.group(4)
        if not verb and not qty_str1 and not qty_str2:
            continue
        qty_str = qty_str1 or qty_str2
        qty = _parse_quantity(qty_str)
        if name not in seen:
            results.append((name, qty))
            seen.add(name)

    for match in pattern_b.finditer(message):
        name, verb, qty_str = match.group(1), match.group(2), match.group(3)
        if not verb and not qty_str:
            continue
        qty = _parse_quantity(qty_str)
        if name not in seen:
            results.append((name, qty))
            seen.add(name)

    return results


# ---------------------------------------------------------------------------
# 处理器
# ---------------------------------------------------------------------------

async def _handle_confirm_order(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理下单/确认下单/结账类意图。"""
    if not re.search(r"(确认下单|我要下单|下单|结账|付款|提交订单)", message):
        return None
    if not cart:
        return {
            "response": "购物车为空，无法下单。请先添加菜品。",
            "cart": cart,
            "intent": "order",
            "agent": "fast_order",
        }
    try:
        response = await order_service.create_order_from_cart(db, user_id, cart)
        return {
            "response": response,
            "cart": [],
            "intent": "order",
            "agent": "fast_order",
        }
    except Exception as e:
        logger.warning(f"[FastRouter] 快捷确认下单失败，降级到 Agent: {e}")
        return None


async def _handle_add_to_cart(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理直接报菜名加购，支持单条消息多道菜。"""
    orders = _extract_dish_orders(message)
    if not orders:
        return None

    added: List[Tuple[str, int]] = []
    try:
        for name, qty in orders:
            item = await menu_service.get_item_by_name(db, name)
            if not item:
                continue
            existing = next((i for i in cart if i.get("name") == item.name), None)
            if existing:
                existing["quantity"] += qty
            else:
                cart.append({
                    "name": item.name,
                    "quantity": qty,
                    "unit_price": float(item.price),
                    "menu_item_id": item.id,
                })
            added.append((item.name, qty))

        if not added:
            return None

        names_text = "、".join([f"{n} x{q}" for n, q in added])
        return {
            "response": f"已为您添加：{names_text}。\n\n{_format_cart(cart)}",
            "cart": cart,
            "intent": "order",
            "agent": "fast_order",
        }
    except Exception as e:
        logger.warning(f"[FastRouter] 快捷加购失败，降级到 Agent: {e}")
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
        "agent": "fast_inquiry",
    }


async def _handle_recommend(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理推荐菜品类意图。"""
    if not re.search(r"(推荐|有什么好吃的|招牌菜|热销|热卖|特色菜)", message):
        return None
    top_dishes = await get_top_selling_dishes(db, 5) if db else []
    response = _format_top_dishes(top_dishes, "为您推荐本店热销 TOP5 菜品：")
    return {
        "response": response,
        "cart": cart,
        "intent": "recommend",
        "agent": "fast_recommend",
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
        "agent": "fast_service",
    }


async def _handle_view_cart(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理查看购物车类意图（排除清空购物车）。"""
    if "清空" in message or not re.search(r"(看看购物车|查看购物车|购物车|cart)", message):
        return None
    return {
        "response": _format_cart(cart),
        "cart": cart,
        "intent": "order",
        "agent": "fast_order",
    }


async def _handle_clear_cart(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理清空购物车类意图。"""
    if not re.search(r"(清空购物车|清空|全部删除)", message):
        return None
    return {
        "response": "购物车已清空。",
        "cart": [],
        "intent": "order",
        "agent": "fast_order",
    }


async def _handle_faq(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理常见 FAQ 直接匹配。"""
    text = message.strip()

    # 营业时间
    if re.search(r"营业时间|几点开门|几点关门|开到几点", text):
        return {
            "response": "本店营业时间为：午餐 11:00-14:30，晚餐 17:00-22:00。周末及节假日中午延长至15:00。厨房最后接单时间为闭餐前30分钟。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 配送
    if re.search(r"配送范围|配送费|外卖|送不送|多久送到", text):
        return {
            "response": "本店支持外卖配送，配送范围为门店周边5公里。3公里内免配送费，3-5公里配送费5元，满68元免配送费。配送时间约30-45分钟。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 电话/预订
    if re.search(r"电话|预订|预约|怎么订|联系方式", text):
        return {
            "response": "预订/咨询电话：010-1234-5678。您也可以通过微信公众号或美团平台在线预订。包间需提前2天预订。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 会员
    if re.search(r"会员|积分|优惠|折扣|等级", text):
        return {
            "response": "本店会员分普通、银卡、金卡、钻石四个等级。消费1元积1分，100积分可抵扣1元。银卡享9.5折，金卡享9折，钻石享8.5折。新会员注册送50积分和酸梅汤券。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 精确 FAQ 匹配
    faq_map = _load_faq_keywords()
    for question, answer in faq_map.items():
        if question in text or text in question:
            return {
                "response": answer,
                "cart": cart,
                "intent": "service",
                "agent": "fast_service",
            }

    return None


# 快速通道处理器列表（按优先级排序）
_FAST_HANDLERS = [
    _handle_confirm_order,
    _handle_clear_cart,
    _handle_view_cart,
    _handle_add_to_cart,
    _handle_view_menu,
    _handle_recommend,
    _handle_query_orders,
    _handle_faq,
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
    未命中时返回 None，调用方应继续走 LLM 分类器或多智能体图。
    """
    text = message.strip()
    if not text:
        return None

    # 混合意图消息直接交给 Agent，避免快速通道只处理一半
    if _has_mixed_intent(text):
        logger.info("[FastRouter] 检测到混合意图，交由 Agent 处理")
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
