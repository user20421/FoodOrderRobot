"""
LangGraph 多智能体工作流构建器

流程:
  start → supervisor (意图识别) → [条件路由] → specialist_agent → END
                                          ↓
                                    service_agent (兜底)
"""
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from app.ai.graph.state import AgentState
from app.ai.graph.parsers import parse_date_from_message, parse_order_intent
from app.ai.graph.context import get_top_selling_dishes, enrich_cart
from app.ai.agents import get_supervisor_agent, AGENT_MAP
from app.ai.prompts.templates import build_dynamic_context
from app.ai.utils import extract_user_message, get_message_role, get_message_content
from app.ai.rag import rag_engine
from app.core.logging_config import get_logger
from app.core.database import AsyncSessionLocal
from app.repositories.order_repo import order_repo
from app.services.order_service import (
    create_order_from_cart,
    format_order_line,
    format_order_list,
)

logger = get_logger(__name__)

# 全局图实例
_agent_graph = None


def _is_checkout_message(message: str) -> bool:
    """判断用户消息是否为确认下单"""
    if not message:
        return False
    keywords = ["确认下单", "确认订单", "我要下单", "现在下单", "提交订单", "去下单", "付款", "结账", "买单"]
    lowered = message.lower()
    return any(kw in lowered for kw in keywords)


def _is_dish_mentioned_by_user(dish_name: str, user_message: str) -> bool:
    """检查菜品名称是否在用户消息中被明确提及"""
    if not dish_name or not user_message:
        return False

    um = user_message.lower()
    dn = dish_name.lower()

    # 完整菜名匹配
    if dn in um:
        return True

    # 去除常见修饰前缀后的核心词匹配
    prefixes = ["招牌", "秘制", "特色", "经典", "传统", "家常", "干锅", "水煮",
                "红烧", "麻辣", "香辣", "蒜蓉", "糖醋", "酸辣", "老坛", "川味",
                "重庆", "北京", "东北", "广式", "清蒸", "干煸", "鱼香", "怪味"]
    core_name = dn
    for p in prefixes:
        if core_name.startswith(p.lower()):
            core_name = core_name[len(p):]
            break

    # 去除括号及后面的内容
    for sep in ["（", "(", "【", "[", "·", " "]:
        if sep in core_name:
            core_name = core_name.split(sep)[0]

    core_name = core_name.strip()
    if core_name and core_name in um and len(core_name) >= 2:
        return True

    return False


async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """Supervisor节点：识别意图"""
    messages = state.get("messages", [])
    user_message = extract_user_message(messages)
    history = []

    for msg in messages:
        role = get_message_role(msg)
        content = get_message_content(msg)
        if role in ("user", "assistant"):
            history.append({"role": role, "content": content})

    if not user_message:
        logger.warning("[Supervisor] 未提取到用户消息，使用兜底回复")
        return {
            "user_intent": "service",
            "active_agent": "service",
            "response": "您好，请问有什么可以帮您？",
        }

    # 调用Supervisor分类意图
    try:
        result = await get_supervisor_agent().classify_intent(user_message, history[:-1] if history else [])
        intent = result.get("agent", "service")
        logger.info(f"[Supervisor] 意图识别: '{user_message[:30]}...' -> {intent}")
    except Exception as e:
        logger.error(f"[Graph] Supervisor失败: {e}")
        intent = "service"

    return {
        "user_intent": intent,
        "active_agent": intent,
    }


async def agent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """专业Agent节点：执行具体任务"""
    agent_name = state.get("active_agent", "service")
    messages = state.get("messages", [])
    cart = state.get("cart", [])
    user_id = state.get("user_id", 0)
    summary = state.get("summary", "")
    user_profile = state.get("user_profile", "")

    # 从 RunnableConfig 获取请求级数据库会话，确保 Graph 内所有 DB 操作在同一个事务中
    db = config.get("configurable", {}).get("db_session") if config else None
    if db is None:
        logger.warning("[AgentNode] 未从 config 获取到 db_session，将使用独立会话（可能破坏事务一致性）")

    # 提取用户最新消息
    user_message = extract_user_message(messages)
    history = []
    for msg in messages:
        role = get_message_role(msg)
        content = get_message_content(msg)
        if role in ("user", "assistant"):
            history.append({"role": role, "content": content})

    if not user_message:
        logger.warning("[Agent] 未提取到用户消息，使用兜底回复")
        return {"response": "您好，请问有什么可以帮您？", "cart": cart}

    # 获取对应Agent
    agent = AGENT_MAP.get(agent_name, AGENT_MAP["service"])
    logger.info(f"[Agent] 路由到 {agent_name} Agent, 用户消息: '{user_message[:30]}...'")

    # 代码层兜底：用户明确说"确认下单"时，直接执行下单逻辑，不依赖LLM的工具调用判断
    if agent_name == "order" and _is_checkout_message(user_message) and cart:
        if db is None:
            async with AsyncSessionLocal() as db:
                result = await create_order_from_cart(db, user_id, cart)
        else:
            result = await create_order_from_cart(db, user_id, cart)
        return {
            "response": result,
            "cart": [],
            "agent_outputs": {agent_name: result},
        }

    # 查看菜单特殊处理：直接返回销量Top10 + 跳转链接，不走LLM（更可靠、更快）
    if agent_name == "inquiry":
        menu_keywords = ["查看菜单", "菜单一览", "菜单有哪些", "全部菜品", "所有菜品"]
        if any(kw in user_message for kw in menu_keywords):
            top_dishes = await get_top_selling_dishes(db, 10) if db else []
            if top_dishes:
                lines = []
                for i, dish in enumerate(top_dishes, 1):
                    # 用 tags 生成极简描述（如：招牌·麻辣·鱼）
                    tags = dish.get("tags", "")
                    if tags:
                        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                        short_desc = "·".join(tag_list[:3]) if tag_list else ""
                    else:
                        short_desc = ""
                    if short_desc:
                        lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）- {short_desc}")
                    else:
                        lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）")
                response = "本店销量TOP10热门菜品：\n" + "\n".join(lines)
            else:
                response = "本店有丰富多样的菜品供您选择。"
            response += "\n\n[点击浏览完整菜单](/menu)"
            logger.info(f"[Agent] 查看菜单直接回复，Top10菜品数: {len(top_dishes)}")
            return {
                "response": response,
                "cart": cart,
                "agent_outputs": {"inquiry": response},
            }

    # 订单查询兜底：LLM 理解意图 → 代码查询真实数据 → 返回格式化结果
    # 彻底避免 LLM 编造假订单，同时利用 LLM 的语言理解能力处理各种复杂说法
    order_query_keywords = ["查询我的订单", "查看我的订单", "我的订单", "所有订单", "订单记录", "查询订单", "查看订单", "订单"]
    is_order_query = any(kw in user_message for kw in order_query_keywords)
    if is_order_query:
        # Step 1: LLM 解析意图（只理解语言，不接触数据）
        intent = await parse_order_intent(user_message)
        logger.info(f"[Agent] 订单查询意图解析: {intent}")

        # Step 2: 代码查询真实数据
        if db is None:
            async with AsyncSessionLocal() as db:
                orders = await order_repo.get_by_user(db, user_id, limit=50)
        else:
            orders = await order_repo.get_by_user(db, user_id, limit=50)
        if not orders:
            result = "您还没有订单记录。"
        else:
            # 按日期筛选
            target_date = intent.get("date")
            if target_date:
                try:
                    from datetime import datetime as dt
                    td = dt.strptime(target_date, "%Y-%m-%d").date()
                    filtered = [o for o in orders if hasattr(o, 'created_at') and o.created_at.date() == td]
                    if not filtered:
                        result = f"{td.strftime('%Y年%m月%d日')}没有订单记录。"
                    else:
                        result = format_order_list(filtered, title=f"{td.strftime('%Y年%m月%d日')}的订单如下：")
                except Exception:
                    result = format_order_list(orders[:intent["limit"]], title="您最近的订单如下：")
            else:
                # 按排序和数量截取
                sorted_orders = list(orders)
                if intent["sort"] == "asc":
                    sorted_orders = sorted_orders[::-1]  # 反转，最旧在前
                sliced = sorted_orders[:intent["limit"]]

                if intent["single"]:
                    result = f"您{'最近' if intent['sort'] == 'desc' else '最早'}的一次订单详情：\n{format_order_line(sliced[0])}"
                elif intent["limit"] == 1:
                    result = f"您{'最近' if intent['sort'] == 'desc' else '最早'}的一次订单详情：\n{format_order_line(sliced[0])}"
                else:
                    title = "您最近的订单如下：" if intent["sort"] == "desc" else "您最早的订单如下："
                    result = format_order_list(sliced, title=title)

        logger.info(f"[Agent] 订单查询直接回复，用户{user_id}，参数: {intent}")
        return {
            "response": result,
            "cart": cart,
            "agent_outputs": {"service": result},
        }

    # 构建动态上下文
    dynamic_context = build_dynamic_context(cart, user_id, summary, user_profile)

    # 如果agent需要RAG上下文，先检索
    rag_context = ""
    if agent_name in ["inquiry", "recommend", "service"]:
        try:
            rag_context = await rag_engine.query(
                user_message,
                history=history[-4:] if len(history) > 1 else None,
            )
            if rag_context and rag_context != "未找到相关信息。":
                dynamic_context += f"\n\n## 相关知识\n{rag_context}"
        except Exception as e:
            logger.warning(f"[Graph] RAG检索失败: {e}")

    # 构建context，把请求级 db_session 注入 Agent，保证 Agent 内下单/查单与当前事务一致
    context = {
        "dynamic_context": dynamic_context,
        "history": history[:-1] if len(history) > 1 else [],
        "cart": cart,
        "user_id": user_id,
        "rag_context": rag_context,
        "db_session": db,
    }

    # 保存旧购物车快照，用于对比新增项
    old_cart_names = {c.get("name", "").lower() for c in (cart or [])}

    # 执行Agent
    try:
        response, new_cart = await agent.run(user_message, context=context)
    except Exception as e:
        logger.error(f"[Graph] Agent执行失败: {e}")
        response = "抱歉，服务暂时异常，请稍后再试。"
        new_cart = cart

    # 代码层兜底：拦截LLM把推荐过的菜误加入购物车（推荐≠订单）
    if agent_name == "order" and new_cart:
        filtered_cart = []
        removed_names = []
        for item in new_cart:
            name = item.get("name", "")
            name_lower = name.lower()
            # 只检查新增项
            if name_lower not in old_cart_names:
                if _is_dish_mentioned_by_user(name, user_message):
                    filtered_cart.append(item)
                else:
                    removed_names.append(name)
                    logger.warning(f"[CartGuard] 拦截幻觉加购: '{name}' 不在用户消息 '{user_message}' 中")
            else:
                filtered_cart.append(item)

        if removed_names:
            new_cart = filtered_cart
            # 重写回复：基于过滤后的正确购物车生成标准摘要，替换LLM的幻觉回复
            cart_lines = [f"{c.get('name', '未知')} x{c.get('quantity', 1)}" for c in new_cart]
            if new_cart:
                response = f"已为您添加菜品到购物车。当前购物车：{ '、'.join(cart_lines) }"
            else:
                response = "已为您处理请求。购物车目前为空。"

    # 幻觉拦截：LLM 没调用 confirm_order 却告诉用户"订单已确认"
    if agent_name == "order" and new_cart and not _is_checkout_message(user_message):
        fake_confirm_keywords = ["订单已确认", "已提交为正式订单", "下单成功", "订单已提交"]
        lowered_resp = (response or "").lower()
        if any(kw in lowered_resp for kw in fake_confirm_keywords):
            logger.warning(f"[Graph] 拦截LLM幻觉: 用户未确认下单但回复包含'{[k for k in fake_confirm_keywords if k in lowered_resp]}'")
            # 构建购物车摘要替换幻觉文本
            cart_lines = [f"• {c.get('name', '未知')} x{c.get('quantity', 1)}" for c in new_cart]
            response = "已为您添加菜品到购物车。\n\n当前购物车：\n" + "\n".join(cart_lines)

    # 补充购物车价格信息
    enriched_cart = await enrich_cart(db, new_cart) if db else new_cart

    return {
        "response": response,
        "cart": enriched_cart,
        "agent_outputs": {agent_name: response},
    }


def route_by_intent(state: AgentState) -> str:
    """根据意图路由到对应Agent"""
    intent = state.get("user_intent", "service")
    if intent in AGENT_MAP:
        return "agent"
    return "agent"


def build_graph() -> StateGraph:
    """构建多智能体图"""
    builder = StateGraph(AgentState)

    # 添加节点
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("agent", agent_node)

    # 设置入口
    builder.set_entry_point("supervisor")

    # supervisor -> agent
    builder.add_edge("supervisor", "agent")

    # agent -> END
    builder.add_edge("agent", END)

    return builder.compile()


def get_agent_graph():
    """获取全局图实例"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_graph()
    return _agent_graph
