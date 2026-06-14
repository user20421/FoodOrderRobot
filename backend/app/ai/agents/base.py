"""
Agent 基类
封装通用的 Tool Calling 逻辑，所有真实的数据库操作委托给 service 层。
"""
import json
from typing import List, Dict, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.ai.llm import get_llm
from app.core.logging_config import get_logger
from app.services.order_service import create_order_from_cart, format_user_orders, format_order_detail

logger = get_logger(__name__)


class BaseToolAgent:
    """基础工具调用智能体"""

    def __init__(self, name: str, system_prompt: str, tools: List[BaseTool], temperature: float = 0.1):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.tools_by_name = {tool.name: tool for tool in tools}
        self.llm = get_llm(temperature=temperature)
        self.model_with_tools = self.llm.bind_tools(tools)

    async def run(self, user_message: str, context: dict = None, max_iterations: int = 5) -> Tuple[str, List[Dict]]:
        """
        执行 Tool Calling 循环
        返回: (response_text, updated_cart)
        """
        context = context or {}
        cart = list(context.get("cart", []))
        messages = [SystemMessage(content=self._build_prompt(context))]

        # 添加历史消息
        # 关键修复：不传入 assistant 的历史消息给 LLM。
        # 原因：ChatTongyi 的 bind_tools 在对话历史中存在无 tool_calls 的 AIMessage 时，
        # 会抑制后续工具调用（LLM 会模仿之前"只回复文字不调用工具"的错误行为）。
        # 对于点餐场景，assistant 的历史文字回复对理解当前意图帮助极小，
        # 真正重要的是：用户说了什么 + 当前购物车状态 + 对话摘要（已在 system prompt 中注入）。
        history = context.get("history", [])
        for h in history[-6:]:
            role = h.get("role", "")
            content = h.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            # assistant 历史消息不传入 messages，避免污染 LLM 的工具调用行为

        messages.append(HumanMessage(content=user_message))

        # Tool Calling 循环
        for iteration in range(max_iterations):
            try:
                response = await self.model_with_tools.ainvoke(messages)
                messages.append(response)

                # 检查是否有工具调用
                if not response.tool_calls:
                    return response.content, cart

                # 如果本轮同时调用了 confirm_order 和购物车工具，优先处理 confirm_order，忽略购物车工具
                has_confirm_order = any(tc["name"] == "confirm_order" for tc in response.tool_calls)

                for tool_call in response.tool_calls:
                    name = tool_call["name"]
                    if has_confirm_order and name in ("add_to_cart", "update_cart_quantity", "remove_from_cart", "clear_cart"):
                        messages.append(ToolMessage(
                            content="已提交订单，购物车不再修改",
                            tool_call_id=tool_call["id"],
                        ))
                        continue

                    tool_result = await self._execute_tool(tool_call, context, cart)
                    messages.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call["id"],
                    ))

            except KeyError as e:
                # DashScope SDK bug: API错误时 KeyError('request')
                if str(e) == "'request'":
                    logger.error(f"[{self.name}] 调用大模型服务失败，可能是 API Key 无效或模型不可用")
                else:
                    logger.error(f"[{self.name}] KeyError: {e}")
                return "抱歉，AI服务暂时不可用，请稍后重试。", cart
            except Exception as e:
                logger.error(f"[{self.name}] 执行失败: {e}")
                return "抱歉，处理您的请求时出现了问题，请稍后再试。", cart

        # 如果达到最大迭代次数，返回最后一条消息
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content, cart
        return "抱歉，这个问题比较复杂，我没能处理好。", cart

    def _build_prompt(self, context: dict) -> str:
        """构建系统提示词"""
        prompt = self.system_prompt

        # 注入动态上下文
        dynamic = context.get("dynamic_context", "")
        if dynamic:
            prompt += f"\n\n{dynamic}"

        return prompt

    async def _execute_tool(self, tool_call: dict, context: dict, cart: List[Dict]) -> str:
        """执行单个工具调用"""
        name = tool_call["name"]
        args = tool_call.get("args", {})

        tool = self.tools_by_name.get(name)
        if not tool:
            return f"工具 '{name}' 不存在"

        try:
            # 购物车类工具：先本地执行状态更新，再调用工具获取返回文本
            if name in ("add_to_cart", "update_cart_quantity", "remove_from_cart", "clear_cart"):
                result = await tool.ainvoke(args)
                # 解析结果更新购物车状态
                await self._update_cart_from_tool(name, args, result, cart)
                return str(result)

            # 确认下单：委托给 service 层，传入请求级 db_session
            if name == "confirm_order":
                db = context.get("db_session")
                if db is None:
                    logger.error(f"[{self.name}] confirm_order 未获取到 db_session")
                    return "系统错误：未找到数据库会话，无法下单。"
                user_id = context.get("user_id", 0)
                return await create_order_from_cart(db, user_id, cart)

            # 查询订单列表：委托给 service 层
            if name == "get_my_orders":
                db = context.get("db_session")
                if db is None:
                    return "系统错误：未找到数据库会话。"
                user_id = context.get("user_id", 0)
                limit = max(args.get("limit", 10), 20)
                return await format_user_orders(db, user_id, limit)

            # 查询订单详情：委托给 service 层
            if name == "get_order_detail":
                db = context.get("db_session")
                if db is None:
                    return "系统错误：未找到数据库会话。"
                order_id = args.get("order_id", 0)
                return await format_order_detail(db, order_id)

            result = await tool.ainvoke(args)
            return str(result)
        except Exception as e:
            logger.warning(f"[{self.name}] 工具执行失败 {name}: {e}")
            return f"工具执行出错: {e}"

    @staticmethod
    async def _update_cart_from_tool(tool_name: str, args: dict, result: str, cart: List[Dict]):
        """根据工具执行结果更新购物车状态"""
        try:
            data = json.loads(result) if isinstance(result, str) else result
            if not isinstance(data, dict):
                return

            if tool_name == "add_to_cart" and data.get("ok") and data.get("cart_item"):
                item = data["cart_item"]
                item_name = item.get("name", "")
                item_qty = item.get("quantity", 1)

                # 优先用 menu_item_id 匹配，其次用 name 匹配，合并所有同名项
                found_indices = []
                for idx, c in enumerate(cart):
                    # menu_item_id 相同 → 同一菜品
                    if c.get("menu_item_id") and item.get("menu_item_id") and c["menu_item_id"] == item["menu_item_id"]:
                        found_indices.append(idx)
                    # 或者名称完全匹配
                    elif c.get("name") == item_name:
                        found_indices.append(idx)

                if found_indices:
                    # 合并到第一个匹配项，删除其余重复项
                    first_idx = found_indices[0]
                    total_qty = sum(cart[i]["quantity"] for i in found_indices) + item_qty
                    cart[first_idx]["quantity"] = total_qty
                    # 更新价格（优先用 item 中已有的）
                    if item.get("unit_price"):
                        cart[first_idx]["unit_price"] = item["unit_price"]
                    if item.get("menu_item_id"):
                        cart[first_idx]["menu_item_id"] = item["menu_item_id"]
                    # 倒序删除其余项，避免索引错乱
                    for i in reversed(found_indices[1:]):
                        cart.pop(i)
                else:
                    cart.append({
                        "menu_item_id": item.get("menu_item_id"),
                        "name": item_name,
                        "quantity": item_qty,
                        "unit_price": item.get("unit_price", 0),
                    })

            elif tool_name == "update_cart_quantity" and data.get("ok"):
                name = data.get("update_name", "")
                qty = data.get("update_quantity", 0)
                for c in cart:
                    if c.get("name") == name or (c.get("menu_item_id") and c["menu_item_id"] == args.get("menu_item_id")):
                        if qty <= 0:
                            cart.remove(c)
                        else:
                            c["quantity"] = qty
                        break

            elif tool_name == "remove_from_cart" and data.get("ok"):
                name = data.get("remove_name", "")
                for c in list(cart):
                    if c.get("name") == name:
                        cart.remove(c)
                        break

            elif tool_name == "clear_cart" and data.get("ok"):
                cart.clear()

        except Exception as e:
            logger.warning(f"[CartUpdate] 更新购物车状态失败: {e}")
