"""
轻量规则快速通道。

对于语义明确、可直接执行的高频意图，先走传统函数快速处理，避免调用大模型，
从而显著降低响应延迟。未命中快速通道的请求再进入 LLM 分类器或多智能体图。

设计原则：
- 确定性业务操作（购物车增删改查、FAQ、菜单/订单查询、简单问候）全部在快速通道完成。
- 快速通道失败时返回 None，由上层降级到 Agent，绝不返回错误响应导致状态丢失。
- 混合意图交给 Agent 统一处理，避免快速通道只回答一半。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.content_loader import get_menu_items, get_faq_data, get_store_docs
from app.services import menu_service, order_service
from app.repositories.order_repo import order_repo
from app.services.menu_service import get_top_selling_dishes

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
# 数量解析
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 购物车动作语义解析
# ---------------------------------------------------------------------------

@dataclass
class CartAction:
    """一次购物车操作意图"""
    action: str  # add | decrease | remove | set | clear | view | confirm
    dish_name: str = ""
    quantity: int = 1
    raw_text: str = ""


# 单位词，用于切分数量与菜品
_UNIT_PATTERN = r"(?:份|个|碗|盘|杯|份儿|个儿|份s?)?"

# 增加类动词：来、上、要、加、点、给我、我要、再来、再要、追加
_ADD_VERBS = r"(?:来|上|要|加|点|给我|我要|再来|再要|再点|追加|上一份|来一份|来一|加一|要一|点一)"

# 减少类动词：减、减掉、减少、去掉、少来、退、退掉
_DECREASE_VERBS = r"(?:减|减掉|减少|去掉|少来|退|退掉|少要|少点)"

# 删除类动词：删、删除、移除、不要、清空、全删
_REMOVE_VERBS = r"(?:删|删除|移除|不要|全删|全部删除|清空)"

# 服务/咨询类关键词
_SERVICE_KEYWORDS = r"营业|配送|会员|优惠|电话|地址|预订|预约|订单|投诉|建议|时间|多久|怎么|做法|是什么|几点|发票|打包|外卖|堂食|座位|包厢|停车|WiFi|无线|网络|折扣|活动|满减|优惠券|代金券|积分|充值|余额|退款|取消|开票|开发票"

# 明确的续点/追加信号，用于在没有报出具体菜名时仍能识别出点餐意图
_STRONG_ORDER_SIGNALS = r"加菜|再点|还要点|再要|再加点|追加|再来一份|还要一份|上一份|来一份|点一个|来一份"


def _has_correction_signal(message: str) -> bool:
    """判断消息是否包含数量/菜品修正信号（如'不对，白米饭是要2份'）。
    此类消息交给 Agent 处理更准确。
    """
    return bool(re.search(r"(不对|错了|不是|改成|改为|其实|应该是|是要)\s*.*?(?:份|个|碗|盘|杯|份儿|个儿)", message))


def _has_mixed_intent(message: str) -> bool:
    """
    判断消息是否同时包含下单/购物车操作意图和服务/咨询意图。
    混合意图消息应交由 Agent 统一处理，避免快速通道只处理一半。

    为了避免误判，这里要求"下单意图"必须是真实的：
    - 消息中明确包含"数量/量词 + 菜品名"，或
    - 包含"加菜/再点/追加"等强点餐信号。
    单纯的语气词（吗/？/可以/能不能）不再被视为服务意图。
    """
    has_service = bool(re.search(_SERVICE_KEYWORDS, message))
    if not has_service:
        return False

    has_order = bool(re.search(_STRONG_ORDER_SIGNALS, message)) or len(_parse_cart_actions(message)) > 0
    return has_order


def _parse_cart_actions(message: str) -> List[CartAction]:
    """
    从消息中提取所有购物车操作意图。
    支持：
      - 增加：来一份麻婆豆腐、加一碗白米饭、我要可乐
      - 减少：减掉一份白米饭、白米饭减一份
      - 删除：删除麻婆豆腐、不要白米饭了、清空购物车
      - 查看：看看购物车、购物车
      - 确认：确认下单、下单、结账
    """
    text = message.strip()
    names = _get_menu_item_names()
    if not names:
        return []

    names_pattern = "|".join(re.escape(n) for n in names)
    qty_pattern = r"[一二两三四五六七八九十\d]+"

    actions: List[CartAction] = []
    seen_positions: set = set()

    # 模式 A：动词 + 可选数量/单位 + 菜品
    # 如"来一份麻婆豆腐"、"减一碗白米饭"、"删掉麻婆豆腐"
    add_verb_group = f"({_ADD_VERBS})"
    dec_verb_group = f"({_DECREASE_VERBS})"
    rem_verb_group = f"({_REMOVE_VERBS})"
    all_verbs = f"{add_verb_group}|{dec_verb_group}|{rem_verb_group}"

    pattern_a = re.compile(
        rf"(?:{all_verbs})\s*({qty_pattern})?\s*(?:份|个|碗|盘|杯|份儿|个儿)?\s*({names_pattern})"
    )

    # 模式 B：菜品 + 动词 + 可选数量/单位
    # 如"麻婆豆腐来一份"、"白米饭减一份"、"可乐不要了"
    pattern_b = re.compile(
        rf"({names_pattern})\s*(?:{all_verbs})\s*({qty_pattern})?\s*(?:份|个|碗|盘|杯|份儿|个儿)?"
    )

    # 模式 C：纯数量+菜品（省略动词）
    # 如"麻婆豆腐一份"、"白米饭一碗"、"两份辣子鸡"——只要菜品在菜单中，即视为 add
    pattern_c = re.compile(
        rf"(?:({names_pattern})\s*({qty_pattern})|({qty_pattern})\s*(?:份|个|碗|盘|杯|份儿|个儿)?\s*({names_pattern}))\s*(?:份|个|碗|盘|杯|份儿|个儿)?"
    )

    def _add_action(action: str, name: str, qty: int, raw: str, pos: int):
        if pos in seen_positions:
            return
        seen_positions.add(pos)
        actions.append(CartAction(action=action, dish_name=name, quantity=qty, raw_text=raw))

    # 模式 A
    for m in pattern_a.finditer(text):
        verb = m.group(1) or m.group(2) or m.group(3)
        qty_str = m.group(4)
        name = m.group(5)
        qty = _parse_quantity(qty_str)
        if _is_add_verb(verb):
            _add_action("add", name, qty, m.group(0), m.start())
        elif _is_decrease_verb(verb):
            _add_action("decrease", name, qty, m.group(0), m.start())
        elif _is_remove_verb(verb):
            # "删掉/删除" + 数量 + 菜名 → 仍然按 remove 处理
            _add_action("remove", name, 0, m.group(0), m.start())

    # 模式 B
    for m in pattern_b.finditer(text):
        name = m.group(1)
        verb = m.group(2) or m.group(3) or m.group(4)
        qty_str = m.group(5)
        qty = _parse_quantity(qty_str)
        if _is_add_verb(verb):
            _add_action("add", name, qty, m.group(0), m.start())
        elif _is_decrease_verb(verb):
            _add_action("decrease", name, qty, m.group(0), m.start())
        elif _is_remove_verb(verb):
            _add_action("remove", name, 0, m.group(0), m.start())

    # 模式 C（只有前面没识别到这道菜时才补充）
    for m in pattern_c.finditer(text):
        # 新正则支持两种形式："麻婆豆腐一份" 或 "两份麻婆豆腐"
        if m.group(1):  # 菜名在前
            name = m.group(1)
            qty_str = m.group(2)
        else:  # 数量在前
            qty_str = m.group(3)
            name = m.group(4)
        qty = _parse_quantity(qty_str)
        # 检查这道菜是否已被模式 A/B 处理过
        already = any(a.dish_name == name for a in actions)
        if not already:
            _add_action("add", name, qty, m.group(0), m.start())

    return actions


def _is_add_verb(verb: str) -> bool:
    return bool(re.match(rf"^{_ADD_VERBS}$", verb.strip()))


def _is_decrease_verb(verb: str) -> bool:
    return bool(re.match(rf"^{_DECREASE_VERBS}$", verb.strip()))


def _is_remove_verb(verb: str) -> bool:
    return bool(re.match(rf"^{_REMOVE_VERBS}$", verb.strip()))


async def _apply_cart_action(
    action: CartAction,
    cart: List[Dict[str, Any]],
    db: AsyncSession,
) -> Optional[str]:
    """执行单个购物车动作，返回操作结果文本；失败返回 None。"""
    if action.action in ("add", "decrease", "remove") and not action.dish_name:
        return None

    try:
        item = await menu_service.get_item_by_name(db, action.dish_name)
        if not item:
            return None
    except Exception as e:
        logger.warning(f"[FastRouter] 查询菜品失败 {action.dish_name}: {e}")
        return None

    existing = next((i for i in cart if i.get("name") == item.name), None)

    if action.action == "add":
        qty = max(1, action.quantity)
        if existing:
            existing["quantity"] += qty
            existing["unit_price"] = float(item.price)
        else:
            cart.append({
                "name": item.name,
                "quantity": qty,
                "unit_price": float(item.price),
                "menu_item_id": item.id,
            })
        return f"{item.name} x{qty}"

    if action.action == "decrease":
        qty = max(1, action.quantity)
        if not existing:
            return None
        if existing["quantity"] <= qty:
            cart.remove(existing)
            return f"已将 {item.name} 从购物车移除"
        existing["quantity"] -= qty
        existing["unit_price"] = float(item.price)
        return f"{item.name} 数量减少 {qty}"

    if action.action == "remove":
        if not existing:
            return None
        cart.remove(existing)
        return f"已将 {item.name} 从购物车移除"

    return None


# ---------------------------------------------------------------------------
# 处理器
# ---------------------------------------------------------------------------

async def _handle_greeting(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理最明确的纯问候，直接返回模板，零 LLM 成本。"""
    text = message.strip()

    # 严格纯问候 pattern（整句只包含问候）
    strict_greeting = re.compile(
        r"^[\s]*(?:"
        r"(?:你|您)好[吗呀]?|"
        r"你好啊|您好啊|"
        r"hello|hi|hey|"
        r"(?:早上|上午|中午|下午|晚上)好|"
        r"(?:在吗|在么|在不在)|"
        r"(?:有人吗)|"
        r"(?:吃了吗)|"
        r"(?:您好)"
        r")[\s\\.!?。！？]*$",
        re.IGNORECASE,
    )

    if not strict_greeting.match(text):
        return None

    return {
        "response": "您好！欢迎来到美味餐厅，我是您的智能点餐助手小餐。请问今天想吃点什么？",
        "cart": cart,
        "intent": "service",
        "agent": "fast_greeting",
    }


def _build_business_hours_reply(text: str) -> str:
    """根据用户询问的时段，返回对应的营业时间。"""
    if re.search(r"下午|晚上|晚餐|傍晚", text):
        return "晚餐营业时间为 17:00-22:00。"
    if re.search(r"上午|中午|午餐|早上", text):
        return "午餐营业时间为 11:00-14:30，周末及节假日中午延长至15:00。"
    return "本店营业时间为：午餐 11:00-14:30，晚餐 17:00-22:00。周末及节假日中午延长至15:00。厨房最后接单时间为闭餐前30分钟。"


def _append_faq_if_needed(text: str, response: str) -> str:
    """如果消息中包含常见 FAQ 关键词，在购物车操作回复后追加 FAQ 回答。
    用于处理"点餐 + 简单咨询"的混合意图，提升快速通道覆盖范围。
    """
    # 营业时间
    if re.search(r"营业时间|几点开门|几点关门|开到几点|什么时候营业|什么时候上班|上班时间|下班", text):
        response += f"\n\n关于营业时间：{_build_business_hours_reply(text)}"
    # 配送
    elif re.search(r"配送范围|配送费|外卖|送不送|多久送到|送到哪里", text):
        response += "\n\n关于配送：本店支持外卖配送，配送范围为门店周边5公里。3公里内免配送费，3-5公里配送费5元，满68元免配送费。配送时间约30-45分钟。"
    # 电话/预订
    elif re.search(r"电话|预订|预约|怎么订|联系方式|订座|包厢", text):
        response += "\n\n关于预订：预订/咨询电话：010-1234-5678。包间需提前2天预订。"
    # 地址/停车
    elif re.search(r"地址|在哪|位置|停车|怎么去|导航", text):
        response += "\n\n关于地址：本店位于美食街88号，地铁3号线美食街站A口出步行约5分钟。店内提供免费停车位。"
    # 会员/优惠
    elif re.search(r"会员|积分|优惠|折扣|等级|充值|代金券|优惠券", text):
        response += "\n\n关于会员：本店会员分普通、银卡、金卡、钻石四个等级。消费1元积1分，100积分可抵扣1元。"
    return response


async def _handle_cart_actions(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """统一处理所有购物车操作（加、减、删、查看、清空、确认下单、批量追加）。"""
    text = message.strip()

    # 0. 购物车批量追加：把购物车现有商品每样再加一份
    if re.search(r"购物车.*(?:再来|再加|追加).*一份|(?:再来|再加|追加).*购物车", text):
        if not cart:
            return {
                "response": "购物车是空的，无法追加。",
                "cart": cart,
                "intent": "order",
                "agent": "fast_order",
            }
        for item in cart:
            await _apply_cart_action(CartAction(action="add", dish_name=item["name"], quantity=1, raw_text=""), cart, db)
        return {
            "response": f"已为您把购物车里的商品各加一份。\n\n{_format_cart(cart)}",
            "cart": cart,
            "intent": "order",
            "agent": "fast_order",
        }

    # 1. 清空购物车
    if re.search(r"^(清空购物车|删除购物车|清掉购物车|清除购物车|清空|清掉|清除|全部删除|全删)$", text) or \
       re.search(r"清掉?\s*购物车\s*(?:里?面?的?|中?的?)?\s*(?:商品|东西|菜品)?", text):
        return {
            "response": "购物车已清空。",
            "cart": [],
            "intent": "order",
            "agent": "fast_order",
        }

    # 2. 查看购物车（排除清空）
    if re.search(r"(看看购物车|查看购物车|购物车|cart)", text) and "清空" not in text:
        return {
            "response": _format_cart(cart),
            "cart": cart,
            "intent": "order",
            "agent": "fast_order",
        }

    # 3. 确认下单
    # 严格匹配：必须包含明确下单词，且前面没有"不要/别/先不/暂时不"等否定词
    confirm_pattern = re.compile(r"(确认下单|我要下单|下单|结账|付款|提交订单)")
    negation_pattern = re.compile(r"(不要|别|先不|暂时不|千万别|不要先|先别).*(?:下单|结账|付款)")
    if confirm_pattern.search(text) and not negation_pattern.search(text):
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

    # 4. 解析加/减/删动作
    actions = _parse_cart_actions(text)
    if not actions:
        return None

    applied: List[str] = []
    failed: List[str] = []
    for action in actions:
        result = await _apply_cart_action(action, cart, db)
        if result:
            applied.append(result)
        else:
            failed.append(action.dish_name or action.raw_text)

    if not applied:
        # 全部失败，交给 Agent 处理（可能是菜品名识别问题）
        return None

    applied_text = "、".join(applied)
    response = f"已为您处理：{applied_text}。\n\n{_format_cart(cart)}"
    if failed:
        response += f"\n\n未能处理的菜品：{', '.join(failed)}，请确认菜名。"

    # 如果消息中还包含常见 FAQ 咨询，追加回答（混合意图快速处理）
    response = _append_faq_if_needed(text, response)

    return {
        "response": response,
        "cart": cart,
        "intent": "order",
        "agent": "fast_order",
    }


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
    """处理查询我的订单类意图。支持"最近N次"，仅展示最近 5 条，超出时提供跳转链接。
    注意：带筛选/分析条件的复杂查询（如"下午下单的有哪些"）交给 Agent 处理。
    """
    # 先排除包含复杂筛选条件的问题
    if re.search(r"(中.*哪些|总价|最高|最低|大于|小于|超过|少于|筛选|过滤)", message):
        return None
    if not re.search(r"(查询我的订单|我的订单|订单记录|历史订单|最近订单|最近.*订单)", message):
        return None

    # 解析"最近N次"中的 N，默认 5
    limit = 5
    m = re.search(r"最近\s*([一二两三四五六七八九十\d]+)\s*次", message)
    if m:
        num_text = m.group(1)
        cn_nums = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        if num_text in cn_nums:
            limit = cn_nums[num_text]
        else:
            limit = int(num_text)
        limit = max(1, min(limit, 10))

    try:
        total = await order_repo.count_by_user(db, user_id)
        orders = await order_repo.get_by_user(db, user_id, limit=limit)
        if not orders:
            response = "您还没有订单记录。"
        else:
            response = order_service.format_order_list(orders, title="您最近的订单如下：", total=total)
    except Exception as e:
        logger.warning(f"[FastRouter] 查询订单失败，降级到 Agent: {e}")
        return None

    return {
        "response": response,
        "cart": cart,
        "intent": "service",
        "agent": "fast_service",
    }


async def _handle_faq(message: str, cart: List[Dict[str, Any]], db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """处理常见 FAQ 直接匹配。"""
    text = message.strip()

    # 营业时间
    if re.search(r"营业时间|几点开门|几点关门|开到几点|什么时候营业|什么时候上班|上班时间|下班", text):
        return {
            "response": _build_business_hours_reply(text),
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 配送
    if re.search(r"配送范围|配送费|外卖|送不送|多久送到|送到哪里", text):
        return {
            "response": "本店支持外卖配送，配送范围为门店周边5公里。3公里内免配送费，3-5公里配送费5元，满68元免配送费。配送时间约30-45分钟。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 电话/预订
    if re.search(r"电话|预订|预约|怎么订|联系方式|订座|包厢", text):
        return {
            "response": "预订/咨询电话：010-1234-5678。您也可以通过微信公众号或美团平台在线预订。包间需提前2天预订。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 地址/停车
    if re.search(r"地址|在哪|位置|停车|怎么去|导航", text):
        return {
            "response": "本店位于美食街88号，地铁3号线美食街站A口出步行约5分钟。店内提供免费停车位，周末建议提前预约。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 会员/优惠
    if re.search(r"会员|积分|优惠|折扣|等级|充值|代金券|优惠券", text):
        return {
            "response": "本店会员分普通、银卡、金卡、钻石四个等级。消费1元积1分，100积分可抵扣1元。银卡享9.5折，金卡享9折，钻石享8.5折。新会员注册送50积分和酸梅汤券。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 发票
    if re.search(r"发票|开票|报销|电子发票", text):
        return {
            "response": "本店支持开具电子发票，下单后可在订单详情页申请开票，或联系店员为您处理。发票内容默认为「餐饮服务」。",
            "cart": cart,
            "intent": "service",
            "agent": "fast_service",
        }

    # 打包/外卖
    if re.search(r"打包|带走|外带|外卖", text):
        return {
            "response": "本店支持堂食、外带和外卖。外带和外卖订单会妥善打包，热菜建议尽快食用以保证口感。",
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
# 1. 简单问候（零成本）
# 2. 购物车操作（高频）
# 3. FAQ（高频）
# 4. 菜单/推荐/订单查询
# 注：复杂问候/身份询问仍交给 LLM 分类器处理
_FAST_HANDLERS = [
    _handle_greeting,
    _handle_cart_actions,
    _handle_faq,
    _handle_view_menu,
    _handle_recommend,
    _handle_query_orders,
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

    # 数量/菜品修正信号交给 Agent 处理，避免规则只处理一半或处理错误
    if _has_correction_signal(text):
        logger.info("[FastRouter] 检测到修正信号，交由 Agent 处理")
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
