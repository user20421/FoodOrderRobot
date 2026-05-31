"""
Order Agent - 点餐智能体
"""
from app.ai.agents.base import BaseToolAgent
from app.ai.tools import CART_TOOLS, ORDER_TOOLS, MENU_TOOLS
from app.ai.prompts.templates import ORDER_AGENT_SYSTEM_PROMPT


class OrderAgent(BaseToolAgent):
    """点餐智能体"""

    def __init__(self):
        super().__init__(
            name="order",
            system_prompt=ORDER_AGENT_SYSTEM_PROMPT,
            tools=CART_TOOLS + ORDER_TOOLS + [MENU_TOOLS[2]],  # cart + order + get_dish_info
            temperature=0.1,
        )


order_agent = OrderAgent()
