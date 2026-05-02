"""
Tool Calling 工具集
所有工具使用 @tool 装饰器注册，供大模型自主选择和调用

设计原则：
1. 每个工具职责单一、描述清晰
2. 返回 JSON 字符串（包含 ok/message/数据），便于 LangGraph 解析和用户阅读
3. 购物车操作类工具返回 cart_item，由 ToolNode 合并到状态中
"""
import json
import os
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from app.ai.tools.menu_tools import (
    get_all_menu_items,
    search_dishes_by_name,
    get_dish_detail,
    search_by_preference,
    get_signature_dishes,
    check_stock,
    get_full_menu_text,
    get_menu_summary,
    format_dish_list,
    format_dish_detail,
)
from app.ai.tools.order_tools import (
    get_user_orders,
    get_order_detail,
    get_latest_order,
    merge_cart,
    get_cart_summary,
    validate_cart_stock,
    submit_order,
    format_order_list,
    format_order_detail,
)
from app.ai.tools.system_tools import get_system_info, detect_info_intent
from app.ai.rag import query_rag


# ------------------------------------------------------------------
# 菜单查询类工具
# ------------------------------------------------------------------

@tool
async def get_menu() -> str:
    """
    获取本店完整菜单，返回 Markdown 表格格式的菜品列表。
    当用户想看菜单、问"有什么菜"时使用此工具。
    """
    text = await get_full_menu_text()
    return json.dumps({"ok": True, "message": text}, ensure_ascii=False)


@tool
async def search_dishes(query: str) -> str:
    """
    按关键词搜索菜品。当用户提到某道菜的名字但不确定是否有时使用。
    Args:
        query: 搜索关键词，如"宫保鸡丁"
    """
    results = await search_dishes_by_name(query)
    if not results:
        return json.dumps({"ok": False, "message": f"没有找到与 '{query}' 相关的菜品。"}, ensure_ascii=False)

    lines = [f"找到 {len(results)} 道相关菜品："]
    for it in results:
        spicy = "[辣]" * it.spicy_level if it.spicy_level else "[不辣]"
        stock_text = "已售罄" if it.stock == 0 else f"库存{it.stock}"
        lines.append(f"  {it.name} {spicy} {it.price}元 ({stock_text})")
    return json.dumps({"ok": True, "message": "\n".join(lines)}, ensure_ascii=False)


@tool
async def get_dish_info(dish_name: str) -> str:
    """
    获取指定菜品的详细信息（价格、辣度、描述、库存等）。
    当用户询问"某菜多少钱""某菜辣不辣""介绍一下某菜"时使用。
    Args:
        dish_name: 菜品名称，如"宫保鸡丁"
    """
    detail = await get_dish_detail(dish_name)
    if not detail:
        return json.dumps({"ok": False, "message": f"本店暂时没有 '{dish_name}' 这道菜。"}, ensure_ascii=False)

    text = format_dish_detail(detail)
    return json.dumps({"ok": True, "message": text}, ensure_ascii=False)


@tool
async def recommend_dishes(
    preference: str = "",
    spicy_level: int = -1,
    category: str = "",
    limit: int = 5,
) -> str:
    """
    根据用户偏好推荐菜品。
    当用户说"推荐几个菜""有什么好吃的""想吃清淡/辣的""适合小孩的"时使用。
    Args:
        preference: 用户偏好描述，如"下饭""清淡""招牌""适合小孩"
        spicy_level: 辣度要求，-1表示不限，0=不辣，1-5递增
        category: 分类要求，如"热菜""素菜""海鲜""汤品""主食"
        limit: 返回数量，默认5道
    """
    from app.ai.tools.parser_tools import extract_preferences

    # 先尝试从 preference 文本解析偏好
    prefs = extract_preferences(preference) if preference else {}
    categories = [category] if category else prefs.get("categories", [])
    tags = prefs.get("tags", [])
    if preference:
        for tag in ["招牌", "下饭", "清淡", "儿童"]:
            if tag in preference:
                tags.append(tag)

    dishes = await search_by_preference(
        spicy_level=spicy_level if spicy_level >= 0 else prefs.get("spicy_level"),
        categories=categories or None,
        tags=tags or None,
        limit=limit,
    )
    if not dishes or len(dishes) < 3:
        dishes = await get_signature_dishes(limit=limit)

    text = format_dish_list(dishes, title="为您推荐")
    return json.dumps({"ok": True, "message": text}, ensure_ascii=False)


# ------------------------------------------------------------------
# 购物车操作类工具（返回 cart_item，由 ToolNode 合并状态）
# ------------------------------------------------------------------

@tool
async def add_to_cart(dish_name: str, quantity: int = 1) -> str:
    """
    将指定菜品加入购物车。
    当用户说"来一份宫保鸡丁""加购麻婆豆腐""来2份水煮牛肉"时使用。
    Args:
        dish_name: 菜品名称
        quantity: 数量，默认1
    """
    items = await get_all_menu_items()
    # 模糊匹配：支持部分匹配
    matched = None
    for it in items:
        if dish_name in it.name or it.name in dish_name:
            matched = it
            break

    if not matched:
        return json.dumps({"ok": False, "message": f"抱歉，本店没有 '{dish_name}'，您可以搜索菜单确认菜名。"}, ensure_ascii=False)

    if matched.stock < quantity:
        return json.dumps({"ok": False, "message": f"{matched.name} 库存不足，仅剩 {matched.stock} 份。"}, ensure_ascii=False)

    return json.dumps({
        "ok": True,
        "message": f"已将 {matched.name} x{quantity} 加入购物车，单价 {matched.price} 元。",
        "cart_item": {
            "menu_item_id": matched.id,
            "name": matched.name,
            "quantity": quantity,
            "unit_price": matched.price,
        }
    }, ensure_ascii=False)


@tool
async def update_cart_quantity(dish_name: str, quantity: int) -> str:
    """
    修改购物车中指定菜品的数量。
    当用户说"玉米排骨汤减10份""宫保鸡丁改为5份""只要2份""再来一份"时使用。
    如果 quantity=0，等同于移除该菜品。
    Args:
        dish_name: 菜品名称
        quantity: 目标数量，必须大于等于0
    """
    if quantity < 0:
        return json.dumps({"ok": False, "message": "数量不能为负数。"}, ensure_ascii=False)
    return json.dumps({
        "ok": True,
        "message": f"将购物车中 '{dish_name}' 的数量调整为 {quantity}。",
        "update_name": dish_name,
        "update_quantity": quantity,
    }, ensure_ascii=False)


@tool
async def remove_from_cart(dish_name: str) -> str:
    """
    从购物车中完全移除指定菜品（不管当前有多少份）。
    当用户说"不要宫保鸡丁了""删掉某菜""去掉这个"时使用。
    如果用户说"减少几份""改为几份"，请使用 update_cart_quantity 工具。
    Args:
        dish_name: 要移除的菜品名称
    """
    # 返回操作指令，由 ToolNode 执行移除
    return json.dumps({
        "ok": True,
        "message": f"将移除购物车中的 '{dish_name}'。",
        "remove_name": dish_name,
    }, ensure_ascii=False)


@tool
async def view_cart() -> str:
    """
    查看当前购物车内容。当用户问"购物车有什么""我点了什么"时使用。
    返回购物车摘要文本（由 ToolNode 注入实际购物车数据后生成）。
    """
    # 实际购物车内容由 ToolNode 在调用后注入
    return json.dumps({
        "ok": True,
        "message": "当前购物车如下：",
        "action": "view_cart",
    }, ensure_ascii=False)


@tool
async def confirm_order() -> str:
    """
    确认下单。当用户说"确认下单""结账""买单"时使用。
    会校验库存、扣减库存、创建订单。下单成功后购物车清空。
    """
    # 实际下单由 ToolNode 执行（需要 user_id 和当前 cart）
    return json.dumps({
        "ok": True,
        "message": "正在为您提交订单...",
        "action": "confirm_order",
    }, ensure_ascii=False)


# ------------------------------------------------------------------
# 订单查询类工具
# ------------------------------------------------------------------

@tool
async def get_my_orders(limit: int = 10) -> str:
    """
    查询用户的历史订单列表。当用户问"我的订单""我点了什么""消费记录"时使用。
    Args:
        limit: 返回数量，默认10条
    """
    # user_id 由 ToolNode 从 state 注入 config 后获取
    return json.dumps({
        "ok": True,
        "message": "正在查询订单...",
        "action": "get_my_orders",
        "limit": limit,
    }, ensure_ascii=False)


@tool
async def get_order_detail(order_id: int) -> str:
    """
    查询指定订单号的详情。当用户问"订单123的详情"时使用。
    Args:
        order_id: 订单号
    """
    return json.dumps({
        "ok": True,
        "message": f"正在查询订单 {order_id}...",
        "action": "get_order_detail",
        "order_id": order_id,
    }, ensure_ascii=False)


# ------------------------------------------------------------------
# 店铺信息类工具
# ------------------------------------------------------------------

@tool
async def get_store_info(query: str = "") -> str:
    """
    查询店铺信息，如营业时间、配送方式、支付方式、地址等。
    当用户问"你们几点营业""支持外卖吗""怎么付款"时使用。
    Args:
        query: 信息类型，如"营业时间""配送""地址""电话""支付"；留空返回全部信息
    """
    info_type = detect_info_intent(query) if query else None
    text = get_system_info(info_type)
    return json.dumps({"ok": True, "message": text}, ensure_ascii=False)


# ------------------------------------------------------------------
# RAG 知识库检索工具
# ------------------------------------------------------------------

@tool
def rag_search(question: str) -> str:
    """
    检索知识库，获取与问题相关的补充信息。
    当用户的问题可能涉及菜品搭配、营养建议、特殊需求等菜单之外的信息时使用。
    Args:
        question: 用户的问题
    """
    try:
        result = query_rag(question)
    except Exception as e:
        return json.dumps({"ok": False, "message": f"检索失败：{e}"}, ensure_ascii=False)
    return json.dumps({"ok": True, "message": result}, ensure_ascii=False)


# ------------------------------------------------------------------
# 工具列表导出
# ------------------------------------------------------------------

AGENT_TOOLS = [
    get_menu,
    search_dishes,
    get_dish_info,
    recommend_dishes,
    add_to_cart,
    update_cart_quantity,
    remove_from_cart,
    view_cart,
    confirm_order,
    get_my_orders,
    get_order_detail,
    get_store_info,
    rag_search,
]
