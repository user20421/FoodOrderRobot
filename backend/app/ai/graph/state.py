"""
LangGraph 共享状态定义
"""
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """多智能体共享状态"""
    # 对话相关
    messages: Annotated[list, add_messages]  # 消息历史
    user_intent: str                         # Supervisor识别的意图
    active_agent: str                        # 当前执行的Agent
    agent_outputs: Dict[str, Any]            # 各Agent的输出

    # 业务状态
    cart: List[Dict[str, Any]]               # 购物车
    user_id: int                             # 用户ID

    # 上下文
    summary: str                             # 对话摘要
    user_profile: str                        # 用户画像文本
    rag_context: str                         # RAG检索上下文

    # 输出
    response: str                            # 最终响应
    metadata: Dict[str, Any]                 # 元数据
