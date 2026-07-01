"""
LangGraph 多智能体图构建器（Handoff 版）。

使用 langgraph.types.Command 让 Agent 节点自由决定下一步流转，
Supervisor 只做轻量意图分流。
"""
from langgraph.graph import StateGraph, END

from app.ai.graph.state import AgentState
from app.ai.agents.nodes import (
    supervisor_node,
    order_agent,
    inquiry_agent,
    recommend_agent,
    service_agent,
)

_agent_graph = None


def build_graph():
    """构建并编译 handoff 多智能体图。"""
    builder = StateGraph(AgentState)

    # 所有节点
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("order", order_agent)
    builder.add_node("inquiry", inquiry_agent)
    builder.add_node("recommend", recommend_agent)
    builder.add_node("service", service_agent)

    # 入口
    builder.set_entry_point("supervisor")

    # 传统边仅用于 Agent 没有返回 Command 时的兜底结束
    builder.add_edge("order", END)
    builder.add_edge("inquiry", END)
    builder.add_edge("recommend", END)
    builder.add_edge("service", END)

    return builder.compile()


def get_agent_graph():
    """获取编译后的图单例。"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_graph()
    return _agent_graph
