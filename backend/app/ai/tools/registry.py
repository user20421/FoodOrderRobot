"""
Agent 工具注册表。

将 ToolContext 上的方法包装为 LangChain 可调用工具，并按 Agent 维护白名单。
"""
from __future__ import annotations

from typing import List

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.ai.tools.context import ToolContext
from app.ai.tools.rag_search import rag_search as rag_search_tool


class AddToCartInput(BaseModel):
    dish_name: str = Field(description="菜品名称")
    quantity: int = Field(default=1, description="数量，默认为 1")


class UpdateCartInput(BaseModel):
    dish_name: str = Field(description="菜品名称")
    quantity: int = Field(description="新的数量，设为 0 表示移除")


class RemoveFromCartInput(BaseModel):
    dish_name: str = Field(description="菜品名称")


class SearchDishesInput(BaseModel):
    query: str = Field(description="搜索关键词，如'辣的'、'鸡肉'")


class DishNameInput(BaseModel):
    dish_name: str = Field(description="菜品名称")


class RecommendInput(BaseModel):
    preference: str = Field(default="", description="偏好描述，如'不辣'、'海鲜'")
    limit: int = Field(default=5, description="推荐数量")


class OrderIdInput(BaseModel):
    order_id: int = Field(description="订单 ID")


class MinMaxOrdersInput(BaseModel):
    days: int = Field(default=15, description="时间范围（天），默认 15 天")
    min_count: int = Field(default=1, description="返回总价最低的订单数量，默认 1")
    max_count: int = Field(default=1, description="返回总价最高的订单数量，默认 1")


class StoreQueryInput(BaseModel):
    query: str = Field(default="", description="查询内容，如'营业时间'、'配送'")


class HandoffInput(BaseModel):
    agent_name: str = Field(description="目标 Agent 名称：order|inquiry|recommend|service")
    reason: str = Field(default="", description="转交原因")


AGENT_TOOL_MAP = {
    "order": [
        "add_to_cart",
        "update_cart_quantity",
        "remove_from_cart",
        "view_cart",
        "clear_cart",
        "confirm_order",
        "check_stock",
        "get_my_orders",
        "get_order_detail",
        "get_min_max_orders",
        "handoff_to",
    ],
    "inquiry": [
        "get_menu",
        "search_dishes",
        "get_dish_info",
        "check_stock",
        "rag_search",
        "handoff_to",
    ],
    "recommend": [
        "get_recommended_dishes",
        "search_dishes",
        "get_dish_info",
        "rag_search",
        "handoff_to",
    ],
    "service": [
        "get_store_info",
        "get_business_hours",
        "get_membership_info",
        "get_my_orders",
        "get_order_detail",
        "get_min_max_orders",
        "rag_search",
        "greet_user",
        "handoff_to",
    ],
}


def build_tool_definitions(ctx: ToolContext) -> List[BaseTool]:
    """为当前 ToolContext 生成一组已绑定的 LangChain 工具。"""

    @tool(args_schema=AddToCartInput)
    async def add_to_cart(dish_name: str, quantity: int = 1) -> str:
        """将菜品添加到购物车。"""
        return await ctx.add_to_cart(dish_name, quantity)

    @tool(args_schema=UpdateCartInput)
    async def update_cart_quantity(dish_name: str, quantity: int) -> str:
        """修改购物车中菜品的数量。"""
        return await ctx.update_cart_quantity(dish_name, quantity)

    @tool(args_schema=RemoveFromCartInput)
    async def remove_from_cart(dish_name: str) -> str:
        """从购物车中移除指定菜品。"""
        return await ctx.remove_from_cart(dish_name)

    @tool
    async def view_cart() -> str:
        """查看当前购物车内容。"""
        return await ctx.view_cart()

    @tool
    async def clear_cart() -> str:
        """清空购物车。"""
        return await ctx.clear_cart()

    @tool
    async def get_menu() -> str:
        """获取完整菜单列表。"""
        return await ctx.get_menu()

    @tool(args_schema=SearchDishesInput)
    async def search_dishes(query: str) -> str:
        """按关键词搜索菜品。"""
        return await ctx.search_dishes(query)

    @tool(args_schema=DishNameInput)
    async def get_dish_info(dish_name: str) -> str:
        """获取指定菜品的详细信息。"""
        return await ctx.get_dish_info(dish_name)

    @tool(args_schema=DishNameInput)
    async def check_stock(dish_name: str) -> str:
        """查询菜品库存状态。"""
        return await ctx.check_stock(dish_name)

    @tool(args_schema=RecommendInput)
    async def get_recommended_dishes(preference: str = "", limit: int = 5) -> str:
        """获取推荐菜品。"""
        return await ctx.get_recommended_dishes(preference, limit)

    @tool
    async def confirm_order() -> str:
        """确认下单，将购物车提交为正式订单。"""
        return await ctx.confirm_order()

    @tool(args_schema=OrderIdInput)
    async def get_order_detail(order_id: int) -> str:
        """查询指定订单号的详细内容。"""
        return await ctx.get_order_detail(order_id)

    @tool
    async def get_my_orders() -> str:
        """查询当前用户的订单历史。"""
        return await ctx.get_my_orders()

    @tool(args_schema=OrderIdInput)
    async def cancel_order(order_id: int) -> str:
        """取消指定订单。"""
        return await ctx.cancel_order(order_id)

    @tool(args_schema=MinMaxOrdersInput)
    async def get_min_max_orders(days: int = 15, min_count: int = 1, max_count: int = 1) -> str:
        """查询最近 N 天内总价最高/最低的订单。可分别指定返回几条（min_count/max_count）。
        例如用户问"最近10天总价最小的3份订单和总价最高的1份订单"，使用 days=10, min_count=3, max_count=1。"""
        return await ctx.get_min_max_orders(days, min_count, max_count)

    @tool(args_schema=StoreQueryInput)
    async def get_store_info(query: str = "") -> str:
        """查询店铺信息。"""
        return await ctx.get_store_info(query)

    @tool
    async def get_business_hours() -> str:
        """获取营业时间。"""
        return await ctx.get_business_hours()

    @tool
    async def get_membership_info() -> str:
        """获取会员制度信息。"""
        return await ctx.get_membership_info()

    @tool
    async def greet_user() -> str:
        """向用户打招呼。"""
        return await ctx.greet_user()

    @tool(args_schema=HandoffInput)
    async def handoff_to(agent_name: str, reason: str = "") -> str:
        """将对话转交给其他专业 Agent。"""
        return await ctx.handoff_to(agent_name, reason)

    return [
        add_to_cart,
        update_cart_quantity,
        remove_from_cart,
        view_cart,
        clear_cart,
        get_menu,
        search_dishes,
        get_dish_info,
        check_stock,
        get_recommended_dishes,
        confirm_order,
        get_my_orders,
        get_order_detail,
        cancel_order,
        get_min_max_orders,
        get_store_info,
        get_business_hours,
        get_membership_info,
        greet_user,
        handoff_to,
        rag_search_tool,
    ]


def filter_tools_for_agent(all_tools: List[BaseTool], agent_name: str) -> List[BaseTool]:
    """按 Agent 名称过滤可用工具。"""
    allowed = set(AGENT_TOOL_MAP.get(agent_name, []))
    return [t for t in all_tools if t.name in allowed]
