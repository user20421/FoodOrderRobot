"""
Agent 基类
封装通用的Tool Calling逻辑
"""
import json
from typing import List, Dict, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.ai.llm import get_llm
from app.core.logging_config import get_logger

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
        执行Tool Calling循环
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

            # 确认下单：真正创建订单
            if name == "confirm_order":
                return await self._handle_confirm_order(context, cart)

            # 查询订单列表：真正查询数据库
            if name == "get_my_orders":
                return await self._handle_get_my_orders(context, args)

            # 查询订单详情：真正查询数据库
            if name == "get_order_detail":
                return await self._handle_get_order_detail(args)

            result = await tool.ainvoke(args)
            return str(result)
        except Exception as e:
            logger.warning(f"[{self.name}] 工具执行失败 {name}: {e}")
            return f"工具执行出错: {e}"

    @staticmethod
    async def _query_orders_raw(user_id: int, limit: int = 50):
        """查询用户原始订单数据（返回对象列表，供上层灵活处理）"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.order_service import get_user_orders
            async with AsyncSessionLocal() as db:
                orders = await get_user_orders(db, user_id, limit)
                return orders
        except Exception as e:
            logger.error(f"[Order] 查询订单原始数据失败: {e}")
            return []

    @staticmethod
    async def _handle_get_my_orders(context: dict, args: dict) -> str:
        """真正查询用户订单列表（兼容旧版工具调用）"""
        user_id = context.get("user_id", 0)
        limit = max(args.get("limit", 10), 20)
        orders = await BaseToolAgent._query_orders_raw(user_id, limit)
        if not orders:
            return "您还没有订单记录。"
        lines = ["您最近的订单如下："]
        for idx, o in enumerate(orders, 1):
            items_str = "，".join([f"{it.name} x{it.quantity}" for it in o.items])
            time_str = o.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(o.created_at, "strftime") else str(o.created_at)
            from app.utils.formatters import order_status_text
            lines.append(f"{idx}. 订单号：{o.id}，状态：{order_status_text(o.status)}，总价：¥{o.total_price:.2f}，菜品：{items_str}，下单时间：{time_str}")
        return "\n".join(lines)

    @staticmethod
    async def _handle_get_order_detail(args: dict) -> str:
        """真正查询订单详情"""
        order_id = args.get("order_id", 0)
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.order_service import get_order_detail
            async with AsyncSessionLocal() as db:
                order = await get_order_detail(db, order_id)
                if not order:
                    return f"订单 #{order_id} 不存在。"
                items_str = "，".join([f"{it.name} x{it.quantity}" for it in order.items])
                time_str = order.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(order.created_at, "strftime") else str(order.created_at)
                from app.utils.formatters import order_status_text
                return f"订单号：{order.id}，状态：{order_status_text(order.status)}，总价：¥{order.total_price:.2f}，菜品：{items_str}，下单时间：{time_str}"
        except Exception as e:
            logger.error(f"[Order] 查询订单详情失败: {e}")
            return f"查询订单详情失败：{str(e)}"

    @staticmethod
    async def _handle_confirm_order(context: dict, cart: List[Dict]) -> str:
        """处理确认下单，真正创建订单"""
        user_id = context.get("user_id", 0)
        if not cart:
            return "购物车为空，无法下单。请先添加菜品。"

        try:
            from app.services.order_service import create_order
            from app.schemas.order import CartItem
            from app.core.database import AsyncSessionLocal
            from app.repositories.menu_repo import menu_item_repo
            from sqlalchemy import select
            from app.models.menu import MenuItem

            items = []
            skipped_names = []
            async with AsyncSessionLocal() as db:
                # 预加载所有菜单项用于模糊匹配
                all_menu_result = await db.execute(select(MenuItem))
                all_menu_items = all_menu_result.scalars().all()

                for c in cart:
                    menu_item_id = c.get("menu_item_id")
                    name = c.get("name", "")
                    
                    # 如果缺少 menu_item_id，尝试通过名称查询数据库补充
                    if not menu_item_id:
                        menu_item = await menu_item_repo.get_by_name(db, name)
                        # 精确匹配失败，尝试模糊匹配
                        if not menu_item and name:
                            for mi in all_menu_items:
                                if name in mi.name or mi.name in name:
                                    menu_item = mi
                                    break
                        if menu_item:
                            menu_item_id = menu_item.id
                            name = menu_item.name
                        else:
                            skipped_names.append(name)
                            continue  # 跳过无法识别的菜品，而不是直接失败

                    items.append(CartItem(
                        menu_item_id=int(menu_item_id),
                        name=name or "未知菜品",
                        quantity=max(1, int(c.get("quantity", 1))),
                        unit_price=float(c.get("unit_price", 0) or 0),
                    ))

                if not items:
                    return "购物车中没有可识别的菜品，无法下单。请重新添加。"

                order = await create_order(db, user_id, items)
                cart.clear()
                msg = f"订单创建成功！订单号：{order.id}，总价：¥{order.total_price:.2f}。感谢您的订购！"
                if skipped_names:
                    msg += f"（以下菜品无法识别已跳过：{', '.join(skipped_names)}）"
                return msg
        except Exception as e:
            logger.error(f"[Order] 下单失败: {e}")
            return f"下单失败：{str(e)}，请稍后重试或联系服务员。"

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
                
                # 查询数据库补充真实价格和 menu_item_id
                try:
                    from app.core.database import AsyncSessionLocal
                    from app.repositories.menu_repo import menu_item_repo
                    async with AsyncSessionLocal() as db:
                        mi = await menu_item_repo.get_by_name(db, item_name)
                        if mi:
                            item["menu_item_id"] = mi.id
                            item["unit_price"] = float(mi.price)
                except Exception as e:
                    logger.warning(f"[CartUpdate] 查询菜品价格失败: {e}")
                
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
                    # 更新价格（优先用数据库查到的）
                    if item.get("unit_price"):
                        cart[first_idx]["unit_price"] = item["unit_price"]
                    if item.get("menu_item_id"):
                        cart[first_idx]["menu_item_id"] = item["menu_item_id"]
                    # 倒序删除其余项，避免索引错乱
                    for i in reversed(found_indices[1:]):
                        cart.pop(i)
                else:
                    cart.append(item)

            elif tool_name == "update_cart_quantity" and data.get("ok") and data.get("update_name"):
                name = data["update_name"]
                qty = data.get("update_quantity", 0)
                if qty > 0:
                    for c in cart:
                        if c["name"] == name or name in c["name"] or c["name"] in name:
                            c["quantity"] = qty
                            break
                else:
                    cart[:] = [c for c in cart if c["name"] != name and name not in c["name"] and c["name"] not in name]

            elif tool_name == "remove_from_cart" and data.get("ok") and data.get("remove_name"):
                name = data["remove_name"]
                cart[:] = [c for c in cart if c["name"] != name]

            elif tool_name == "clear_cart" and data.get("ok"):
                cart.clear()

        except Exception as e:
            logger.warning(f"[CartUpdate] 解析工具结果失败: {e}")
