"""
AI 核心工具函数
"""
from typing import List, Any
from langchain_core.messages import HumanMessage


def extract_last_user_message(messages: List[Any]) -> str:
    """
    从消息列表中提取最后一条用户消息。
    兼容 dict 和 LangChain Message 对象。
    """
    for msg in reversed(messages or []):
        # LangChain Message 对象
        if isinstance(msg, HumanMessage):
            return str(msg.content or "")

        # dict 格式
        if isinstance(msg, dict):
            role = msg.get("role", "") or msg.get("type", "")
            if role in ("user", "human"):
                return str(msg.get("content", ""))
    return ""
