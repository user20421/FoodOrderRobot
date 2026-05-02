"""
Tool Calling Agent（基于 LangGraph StateGraph）

架构：
  1. StateGraph 管理对话状态（messages + cart + user_id）
  2. LLM（ChatTongyi）绑定工具，自主决策调用哪些工具
  3. 自定义 OrderingToolNode 执行工具并维护购物车状态
  4. 支持多轮工具调用（ReAct 循环）

与旧架构的区别：
  - 旧：Supervisor 硬编码分类 → 5 个独立 Agent 各干各的
  - 新：单一大模型 Agent，通过 Tool Calling 自主选择工具组合完成任务
"""
import json
import os
from typing import TypedDict, Annotated

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.ai.tools.agent_tools import AGENT_TOOLS
from app.ai.tools.menu_tools import get_all_menu_items, format_dish_list
from app.ai.tools.order_tools import (
    get_user_orders,
    get_order_detail,
    get_cart_summary,
    merge_cart,
    validate_cart_stock,
    submit_order,
    format_order_list,
    format_order_detail,
)
from app.core.config import settings


# ------------------------------------------------------------------
# 状态定义
# ------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    cart: list
    user_id: int


# ------------------------------------------------------------------
# LLM 实例（单例，避免重复初始化）
# ------------------------------------------------------------------
_llm_instance = None
_model_with_tools = None

def _get_llm():
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance
    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未设置")
    _llm_instance = ChatTongyi(
        model=settings.chat_model,
        dashscope_api_key=api_key,
        temperature=0.1,
    )
    return _llm_instance


def _get_model_with_tools():
    global _model_with_tools
    if _model_with_tools is not None:
        return _model_with_tools
    llm = _get_llm()
    _model_with_tools = llm.bind_tools(AGENT_TOOLS)
    return _model_with_tools


# ------------------------------------------------------------------
# 系统提示词构建
# ------------------------------------------------------------------
def _build_system_prompt(cart: list, user_id: int) -> str:
    """动态构建系统提示词，注入当前购物车状态"""
    if cart:
        summary = get_cart_summary(cart)
        total = sum(c["unit_price"] * c["quantity"] for c in cart)
        cart_text = f"{summary}（合计 {total} 元）"
    else:
        cart_text = "购物车为空"

    return (
        "你是本店智能点餐机器人小餐。你的任务是通过调用工具帮助用户完成点餐、查询、推荐等操作。\n\n"
        "## 可用工具\n"
        "- get_menu: 获取完整菜单\n"
        "- search_dishes(query): 按关键词搜索菜品\n"
        "- get_dish_info(dish_name): 获取菜品详情（价格、辣度、库存等）\n"
        "- recommend_dishes(preference, spicy_level, category, limit): 根据偏好推荐菜品\n"
        "- add_to_cart(dish_name, quantity=1): 添加菜品到购物车（已有则数量累加）\n"
        "- update_cart_quantity(dish_name, quantity): 修改购物车中菜品的数量（如'减10份''改为5份'）\n"
        "- remove_from_cart(dish_name): 完全移除购物车中的菜品（如'不要了''删掉'）\n"
        "- view_cart(): 查看购物车\n"
        "- confirm_order(): 确认下单（会扣减库存、创建订单、清空购物车）\n"
        "- get_my_orders(limit=10): 查询我的订单历史\n"
        "- get_order_detail(order_id): 查询指定订单详情\n"
        "- get_store_info(query): 查询店铺信息（营业时间、配送等）\n"
        "- rag_search(question): 知识库检索（菜品搭配、营养建议等）\n\n"
        "## 当前状态\n"
        f"用户ID: {user_id}\n"
        f"购物车: {cart_text}\n\n"
        "## 业务规则\n"
        "1. 只能推荐和介绍菜单中真实存在的菜品，绝对不能编造不存在的菜名、价格或描述。\n"
        "2. 点餐时如果库存不足，必须告知用户并建议替代方案。\n"
        "3. 回复简洁自然，像真人服务员一样亲切，不要长篇大论。\n"
        "4. 严禁使用 emoji、颜文字、特殊符号（如辣椒图案、庆祝图案、爱心、火焰等），只使用纯文本和常见标点。\n"
        "5. 用户一次可以点多道菜，你可以多次调用 add_to_cart。\n"
        "6. 用户确认下单前，如果购物车有内容，可以主动提示当前购物车。\n"
        "7. 如果用户只是闲聊（问候、感谢、告别），直接回复，不需要调用工具。\n"
        "8. 确认下单（confirm_order）必须在用户明确同意后才能调用，不要擅自替用户下单。\n"
        "9. 重要：修改购物车的任何操作（加购、移除、下单）必须通过调用对应工具完成。仅靠文本回复无法改变购物车状态。\n"
    )


# ------------------------------------------------------------------
# LLM 节点
# ------------------------------------------------------------------
async def _call_model(state: AgentState):
    """调用绑定了工具的 LLM"""
    model_with_tools = _get_model_with_tools()

    messages = state["messages"]
    # 只在对话开头（第一条是 HumanMessage）注入系统提示词，避免多轮 tool calling 时重复
    if len(messages) == 1 and isinstance(messages[0], HumanMessage):
        system_msg = SystemMessage(content=_build_system_prompt(state["cart"], state["user_id"]))
        messages = [system_msg] + messages

    response = await model_with_tools.ainvoke(messages)
    return {"messages": [response]}


# ------------------------------------------------------------------
# 自定义 ToolNode
# ------------------------------------------------------------------
class OrderingToolNode:
    """
    自定义工具执行节点
    - 调用普通查询工具
    - 拦截购物车/订单类工具，直接访问 state 执行操作
    - 维护购物车状态一致性
    """

    def __init__(self):
        self.tools_by_name = {tool.name: tool for tool in AGENT_TOOLS}

    async def __call__(self, state: AgentState):
        last_msg: AIMessage = state["messages"][-1]
        tool_calls = last_msg.tool_calls

        cart = list(state.get("cart", []))
        user_id = state.get("user_id")
        tool_messages = []

        for tc in tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            tid = tc["id"]

            # --- 购物车/订单状态类工具：直接由节点处理 ---
            if name == "view_cart":
                text = self._handle_view_cart(cart)
                tool_messages.append(ToolMessage(content=text, tool_call_id=tid))
                continue

            if name == "confirm_order":
                text, cart = await self._handle_confirm_order(user_id, cart)
                tool_messages.append(ToolMessage(content=text, tool_call_id=tid))
                continue

            if name == "get_my_orders":
                text = await self._handle_get_my_orders(user_id, args.get("limit", 10))
                tool_messages.append(ToolMessage(content=text, tool_call_id=tid))
                continue

            if name == "get_order_detail":
                text = await self._handle_get_order_detail(args.get("order_id"))
                tool_messages.append(ToolMessage(content=text, tool_call_id=tid))
                continue

            # --- 普通工具：调用 @tool 函数 ---
            tool = self.tools_by_name.get(name)
            if not tool:
                tool_messages.append(
                    ToolMessage(content=f"工具 '{name}' 不存在", tool_call_id=tid)
                )
                continue

            try:
                result = await tool.ainvoke(args)
            except Exception as e:
                result = f"工具执行出错: {e}"

            # 购物车合并：add_to_cart
            if name == "add_to_cart":
                cart = self._merge_add_result(str(result), cart)
                # 把友好的消息提取给 LLM 看
                content = self._extract_message(str(result))
                tool_messages.append(ToolMessage(content=content, tool_call_id=tid))
                continue

            # 购物车更新：update_cart_quantity
            if name == "update_cart_quantity":
                cart = self._merge_update_result(str(result), cart)
                content = self._extract_message(str(result))
                tool_messages.append(ToolMessage(content=content, tool_call_id=tid))
                continue

            # 购物车合并：remove_from_cart
            if name == "remove_from_cart":
                cart = self._merge_remove_result(str(result), cart)
                content = self._extract_message(str(result))
                tool_messages.append(ToolMessage(content=content, tool_call_id=tid))
                continue

            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tid))

        return {"messages": tool_messages, "cart": cart}

    # --- 状态处理辅助方法 ---

    def _handle_view_cart(self, cart: list) -> str:
        if not cart:
            return "购物车是空的，去菜单看看有什么想吃的吧～"
        summary = get_cart_summary(cart)
        total = sum(c["unit_price"] * c["quantity"] for c in cart)
        return f"您的购物车：{summary}\n合计 {total} 元。说'确认下单'即可提交订单。"

    async def _handle_confirm_order(self, user_id: int, cart: list):
        if not cart:
            return "购物车是空的，请先选择菜品后再确认下单哦～", cart

        validation = await validate_cart_stock(cart)
        if not validation["valid"]:
            errors = "\n".join(validation["errors"])
            return f"下单失败：\n{errors}\n请调整后重新确认。", cart

        result = await submit_order(user_id, cart)
        if not result["success"]:
            return f"下单失败：{result['error']}", cart

        order = result["order"]
        item_lines = []
        for c in cart:
            item_lines.append(f"  {c['name']} x{c['quantity']} = {c['unit_price'] * c['quantity']}元")

        text = (
            f"订单已创建成功！\n"
            f"订单号：{order.id}\n"
            + "\n".join(item_lines) + "\n"
            f"总价：{order.total_price}元\n"
            f"感谢您的光临，我们会尽快为您备餐！"
        )
        return text, []  # 清空购物车

    async def _handle_get_my_orders(self, user_id: int, limit: int) -> str:
        orders = await get_user_orders(user_id, limit=limit)
        return format_order_list(orders)

    async def _handle_get_order_detail(self, order_id: int) -> str:
        if not order_id:
            return "请提供订单号。"
        order = await get_order_detail(order_id)
        if not order:
            return f"未找到订单号 {order_id} 的订单。"
        return format_order_detail(order)

    def _merge_add_result(self, result: str, cart: list) -> list:
        try:
            data = json.loads(result)
            if data.get("ok") and data.get("cart_item"):
                return merge_cart(cart, [data["cart_item"]])
        except Exception:
            pass
        return cart

    def _merge_update_result(self, result: str, cart: list) -> list:
        try:
            data = json.loads(result)
            if data.get("ok") and data.get("update_name"):
                name = data["update_name"]
                qty = data.get("update_quantity", 0)
                new_cart = []
                for c in cart:
                    if c["name"] == name or name in c["name"] or c["name"] in name:
                        if qty > 0:
                            new_cart.append({**c, "quantity": qty})
                        # qty == 0 时不加入，即移除
                    else:
                        new_cart.append(c)
                return new_cart
        except Exception:
            pass
        return cart

    def _merge_remove_result(self, result: str, cart: list) -> list:
        try:
            data = json.loads(result)
            if data.get("ok") and data.get("remove_name"):
                name = data["remove_name"]
                return [c for c in cart if c["name"] != name]
        except Exception:
            pass
        return cart

    def _extract_message(self, result: str) -> str:
        try:
            data = json.loads(result)
            return data.get("message", result)
        except Exception:
            return result


# ------------------------------------------------------------------
# 条件边：判断是否需要继续调用工具
# ------------------------------------------------------------------
def _should_continue(state: AgentState):
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tools"
    return END


# ------------------------------------------------------------------
# 构建图
# ------------------------------------------------------------------
def _build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("agent", _call_model)
    builder.add_node("tools", OrderingToolNode())
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile()


_agent_graph = _build_graph()


# ------------------------------------------------------------------
# 对外接口
# ------------------------------------------------------------------
async def run_agent_chat(user_id: int, message: str, cart: list = None) -> dict:
    """
    Tool Calling Agent 主入口

    Args:
        user_id: 用户ID
        message: 用户输入消息
        cart: 当前购物车状态

    Returns:
        {"response": str, "cart": list}
    """
    cart = cart or []

    try:
        result = await _agent_graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "cart": cart,
                "user_id": user_id,
            }
        )
    except Exception as e:
        return {
            "response": f"服务暂时异常，请稍后重试。错误信息：{str(e)[:200]}",
            "cart": cart,
        }

    # 提取最后的 AI 回复
    final_msg = result["messages"][-1]
    if isinstance(final_msg, AIMessage):
        response = final_msg.content
    else:
        response = "抱歉，处理您的请求时出现了问题。"

    return {
        "response": response,
        "cart": result.get("cart", cart),
    }
