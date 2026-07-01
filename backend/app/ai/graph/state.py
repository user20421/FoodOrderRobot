"""
LangGraph 共享状态定义
"""
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Handoff 多智能体共享状态"""
    # 对话相关
    messages: Annotated[list, add_messages]  # 消息历史
    intent: str                              # Supervisor 识别的意图
    current_agent: str                       # 当前执行的 Agent

    # 业务状态
    cart: List[Dict[str, Any]]               # 购物车
    user_id: int                             # 用户ID

    # 上下文
    summary: str                             # 对话摘要
    user_identity: str                       # 用户身份标识（用户名等）

    # 输出
    response: str                            # 最终响应
    metadata: Dict[str, Any]                 # 元数据
