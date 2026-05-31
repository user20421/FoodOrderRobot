"""
Inquiry Agent - 咨询智能体
"""
from app.ai.agents.base import BaseToolAgent
from app.ai.tools import MENU_TOOLS, COMMON_TOOLS
from app.ai.prompts.templates import INQUIRY_AGENT_SYSTEM_PROMPT


class InquiryAgent(BaseToolAgent):
    """咨询智能体"""

    def __init__(self):
        super().__init__(
            name="inquiry",
            system_prompt=INQUIRY_AGENT_SYSTEM_PROMPT,
            tools=MENU_TOOLS + [COMMON_TOOLS[0]],  # menu + rag_search
            temperature=0.1,
        )


inquiry_agent = InquiryAgent()
