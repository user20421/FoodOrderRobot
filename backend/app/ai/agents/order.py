"""
点餐智能体 (OrderAgent)

职责：解析用户点餐意图，管理购物车状态，在确认时创建订单并扣减库存。

适用场景：
  - "来一份宫保鸡丁"
  - "再加个麻婆豆腐"
  - "来2份水煮牛肉"
  - "确认下单"
  - "购物车有什么？"

工具集：
  - extract_dish_names: 从消息中提取菜品和数量
  - merge_cart: 合并购物车
  - get_cart_summary: 购物车摘要
  - validate_cart_stock: 库存校验
  - submit_order: 提交订单
"""
from app.ai.agents.base import BaseAgent
from app.ai.tools import (
    extract_dish_names,
    get_all_menu_items,
    merge_cart,
    get_cart_summary,
    validate_cart_stock,
    submit_order,
)


class OrderAgent(BaseAgent):
    """
    点餐智能体
    负责将用户的自然语言点餐请求转化为购物车操作，并最终提交订单。
    """

    def __init__(self):
        super().__init__(
            name="点餐专员",
            description="解析用户点餐需求、管理购物车、确认下单并扣减库存",
        )

    async def run(self, user_id: int, message: str, cart: list = None) -> dict:
        """
        点餐流程：
        1. 判断是否是确认下单
        2. 若是，校验库存 → 创建订单 → 清空购物车
        3. 若不是，解析消息中的菜品 → 加入购物车
        """
        cart = cart or []

        # 判断是否是确认下单/结账
        if self._is_confirm_order(message):
            return await self._handle_confirm(user_id, cart)

        # 判断是否是查看购物车
        if self._is_check_cart(message):
            return self._handle_check_cart(cart)

        # 解析消息中的菜品请求
        items = await self._parse_items(message)
        if items:
            new_cart = merge_cart(cart, items)
            summary = get_cart_summary(new_cart)
            return {
                "response": f"已加入购物车：{summary}。\n说'确认下单'即可为您下单！",
                "cart": new_cart,
            }

        # 没有识别到菜品，但购物车有东西 → 提示当前购物车
        if cart:
            summary = get_cart_summary(cart)
            return {
                "response": f"当前购物车：{summary}。\n继续加菜或说'确认下单'都可以哦～",
                "cart": cart,
            }

        # 购物车为空且没有识别到菜品
        return {
            "response": "我没有识别到您想点的菜品，可以告诉我菜名吗？例如：来一份宫保鸡丁。",
            "cart": cart,
        }

    def _is_confirm_order(self, message: str) -> bool:
        """判断用户是否在确认下单"""
        confirm_keywords = ["确认", "下单", "结账", "买单", "就这些", "好了", "可以了", "提交"]
        return any(kw in message for kw in confirm_keywords)

    def _is_check_cart(self, message: str) -> bool:
        """判断用户是否在查看购物车"""
        check_keywords = ["购物车", "点了什么", "加了什么", "买了什么", "有哪些"]
        return any(kw in message for kw in check_keywords) and not any(kw in message for kw in ["订单", "历史"])

    def _handle_check_cart(self, cart: list) -> dict:
        """处理查看购物车请求"""
        if not cart:
            return {"response": "购物车是空的，去菜单看看有什么想吃的吧～", "cart": cart}
        summary = get_cart_summary(cart)
        total = sum(c["unit_price"] * c["quantity"] for c in cart)
        return {
            "response": f"您的购物车：{summary}\n合计 {total} 元。说'确认下单'即可提交订单。",
            "cart": cart,
        }

    async def _handle_confirm(self, user_id: int, cart: list) -> dict:
        """处理确认下单请求"""
        if not cart:
            return {"response": "购物车是空的，请先选择菜品后再确认下单哦～", "cart": cart}

        # 库存校验
        validation = await validate_cart_stock(cart)
        if not validation["valid"]:
            errors = "\n".join(validation["errors"])
            return {"response": f"下单失败：\n{errors}\n请调整后重新确认。", "cart": cart}

        # 创建订单
        result = await submit_order(user_id, cart)
        if not result["success"]:
            return {"response": f"下单失败：{result['error']}", "cart": cart}

        order = result["order"]
        item_lines = []
        for c in cart:
            item_lines.append(f"  {c['name']} x{c['quantity']} = {c['unit_price'] * c['quantity']}元")

        response = (
            f"订单已创建成功！\n"
            f"订单号：{order.id}\n"
            + "\n".join(item_lines) + "\n"
            f"总价：{order.total_price}元\n"
            f"感谢您的光临，我们会尽快为您备餐！"
        )
        return {"response": response, "cart": []}

    async def _parse_items(self, message: str) -> list:
        """从消息中解析出要点哪些菜"""
        items = await get_all_menu_items()
        return extract_dish_names(message, items)
