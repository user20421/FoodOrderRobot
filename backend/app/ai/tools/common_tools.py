"""
通用工具
"""
from typing import Optional
from langchain_core.tools import tool


@tool
def rag_search(question: str) -> str:
    """
    知识库检索
    用于回答菜品搭配、营养建议、店铺政策、常见问题等知识性问题
    Args:
        question: 要检索的问题
    """
    return f"RAG检索: {question}"


@tool
def get_user_profile() -> str:
    """获取当前用户的偏好画像"""
    return "请查看state中的user_profile信息。"


@tool
def greet_user() -> str:
    """向用户打招呼，用于欢迎语"""
    return "greet"
