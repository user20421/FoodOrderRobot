"""
店铺与通用工具 Mixin。
"""
from __future__ import annotations


class StoreToolsMixin:
    """店铺/通用工具的共享实现（需配合 ToolContext 使用）。"""

    async def get_store_info(self, query: str = "") -> str:
        """查询店铺信息。"""
        return (
            "本店是一家家常菜餐厅，提供午餐和晚餐服务。\n"
            "营业时间：午餐 11:00-14:30，晚餐 17:00-22:00。\n"
            "配送范围 5 公里，满 68 元免配送费。\n"
            "会员制度：普通/银卡/金卡/钻石，消费满额升级。"
        )

    async def get_business_hours(self) -> str:
        """获取营业时间。"""
        return "营业时间：午餐 11:00-14:30，晚餐 17:00-22:00。"

    async def get_membership_info(self) -> str:
        """获取会员制度信息。"""
        return "会员制度：普通会员/银卡/金卡/钻石会员，消费满额自动升级。"

    async def greet_user(self) -> str:
        """向用户打招呼。"""
        return "您好，欢迎来到美味餐厅，请问今天想吃点什么？"

    async def handoff_to(self, agent_name: str, reason: str = "") -> str:
        """
        将对话转交给其他专业 Agent。
        返回的结果会被 Agent 节点识别并生成 Command(goto=agent_name)。
        """
        return f"[HANDOFF:{agent_name}] {reason}".strip()
