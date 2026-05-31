"""
Service Agent - 客服智能体
"""
from app.ai.agents.base import BaseToolAgent
from app.ai.tools import STORE_TOOLS, ORDER_TOOLS, COMMON_TOOLS
from app.ai.prompts.templates import SERVICE_AGENT_SYSTEM_PROMPT


class ServiceAgent(BaseToolAgent):
    """客服智能体"""

    def __init__(self):
        super().__init__(
            name="service",
            system_prompt=SERVICE_AGENT_SYSTEM_PROMPT,
            tools=STORE_TOOLS + ORDER_TOOLS + COMMON_TOOLS,
            temperature=0.1,
        )


service_agent = ServiceAgent()
