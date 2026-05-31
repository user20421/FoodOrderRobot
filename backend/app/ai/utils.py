"""
AI核心工具函数
"""
from typing import List, Dict, Any, Union
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
)


def extract_user_message(messages: List[Any]) -> str:
    """
    从消息列表中提取最后一条用户消息
    兼容 dict 和 LangChain Message 对象
    """
    for msg in reversed(messages):
        # LangChain Message 对象
        if isinstance(msg, HumanMessage):
            return msg.content or ""
        # dict 格式
        if isinstance(msg, dict):
            if msg.get("role") == "user" or msg.get("type") == "human":
                return msg.get("content", "")
    return ""


def convert_to_langchain_messages(messages: List[Any]) -> List[BaseMessage]:
    """
    将混合格式的消息列表转换为 LangChain Message 对象列表
    兼容 dict / LangChain Message / string
    """
    result = []
    for msg in messages:
        # 已经是 Message 对象
        if isinstance(msg, BaseMessage):
            result.append(msg)
            continue
        # 字符串
        if isinstance(msg, str):
            result.append(HumanMessage(content=msg))
            continue
        # dict 格式
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
            msg_type = msg.get("type", "")

            if role == "user" or msg_type == "human":
                result.append(HumanMessage(content=content))
            elif role == "assistant" or msg_type == "ai":
                result.append(AIMessage(content=content))
            elif role == "system":
                result.append(SystemMessage(content=content))
            elif role == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                result.append(ToolMessage(content=content, tool_call_id=tool_call_id))
            else:
                result.append(HumanMessage(content=content))
    return result


def get_message_role(msg: Any) -> str:
    """获取消息角色"""
    if isinstance(msg, HumanMessage):
        return "user"
    if isinstance(msg, AIMessage):
        return "assistant"
    if isinstance(msg, SystemMessage):
        return "system"
    if isinstance(msg, ToolMessage):
        return "tool"
    if isinstance(msg, dict):
        return msg.get("role", msg.get("type", "unknown"))
    return "unknown"


def get_message_content(msg: Any) -> str:
    """获取消息内容"""
    if isinstance(msg, BaseMessage):
        return msg.content or ""
    if isinstance(msg, dict):
        return msg.get("content", "")
    if isinstance(msg, str):
        return msg
    return ""
