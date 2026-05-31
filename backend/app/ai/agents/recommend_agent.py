"""
Recommend Agent - 推荐智能体
"""
from app.ai.agents.base import BaseToolAgent
from app.ai.tools import MENU_TOOLS, COMMON_TOOLS
from app.ai.prompts.templates import RECOMMEND_AGENT_SYSTEM_PROMPT


class RecommendAgent(BaseToolAgent):
    """推荐智能体"""

    def __init__(self):
        super().__init__(
            name="recommend",
            system_prompt=RECOMMEND_AGENT_SYSTEM_PROMPT,
            tools=MENU_TOOLS + COMMON_TOOLS,  # menu + common
            temperature=0.2,  # 推荐可以稍微有创意
        )


recommend_agent = RecommendAgent()
