"""
Handoff 多智能体节点。

每个 Agent 节点都是一个可返回 langgraph.types.Command 的函数，
通过 Command(goto=...) 实现智能体间的自由转交。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from langchain_core.runnables import RunnableConfig

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.types import Command

from app.ai.llm import get_llm
from app.ai.agents.prompts import PromptBuilder, build_dynamic_context
from app.ai.tools import ToolContext, build_tool_definitions, filter_tools_for_agent
from app.ai.rag.retriever import retrieve_knowledge
from app.ai.utils import extract_last_user_message
from app.core.logging_config import get_logger

logger = get_logger(__name__)

MAX_TOOL_ITERATIONS = 3
MAX_HANDOFFS = 2  # 最多允许 2 次 Agent 间转交，防止踢皮球

# 触发 RAG 检索的关键词（简单语义 guard）
_RAG_TRIGGER_KEYWORDS = [
    "营业时间", "配送", "会员", "优惠", "活动", "退款", "取消", "过敏",
    "辣度", "营养", "热量", "忌口", "小孩", "孕妇", "糖尿病", "高血压",
    "停车", "地址", "电话", "外卖", "自取", "预约", "订座", "包间",
    "faq", "政策", "规则", "说明",
]


def _should_use_rag(user_message: str) -> bool:
    """根据用户消息判断是否值得做一次 RAG 检索。"""
    text = user_message.lower()
    return any(kw in text for kw in _RAG_TRIGGER_KEYWORDS)


def _agent_messages(
    state: Dict[str, Any],
    system_prompt: str,
    agent_name: str,
) -> List[SystemMessage | HumanMessage | AIMessage | ToolMessage]:
    """构建注入业务上下文的 system + 历史消息列表。"""
    system_text = (
        system_prompt
        + f"\n\n## 当前负责智能体\n{agent_name}"
    )

    messages: List[Any] = [SystemMessage(content=system_text)]
    for m in state.get("messages") or []:
        if isinstance(m, dict):
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                continue
            messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
        else:
            messages.append(m)
    return messages


def _parse_tool_calls(message: AIMessage) -> List[Dict[str, Any]]:
    if not hasattr(message, "tool_calls") or not message.tool_calls:
        return []
    return [
        {
            "id": tc.get("id"),
            "name": tc.get("name"),
            "args": tc.get("args") or {},
        }
        for tc in message.tool_calls
    ]


def _build_tool_result_message(tool_call_id: str, content: str) -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=tool_call_id)


async def _run_agent_loop(
    state: Dict[str, Any],
    config: Optional[RunnableConfig],
    agent_name: str,
    allowed_agent_names: Optional[List[str]] = None,
) -> Dict[str, Any] | Command:
    """
    通用 ReAct 循环：调用 LLM -> 执行工具 -> 再调用 LLM。
    支持 handoff_to 工具，命中时返回 Command(goto=target)。
    """
    allowed_agent_names = allowed_agent_names or ["order", "inquiry", "recommend", "service"]

    # 读取 handoff 历史，用于检测循环和限制次数
    metadata = state.get("metadata") or {}
    handoff_path = list(metadata.get("handoff_path") or [])
    handoff_count = int(metadata.get("handoff_count") or 0)

    # 服务型/咨询型问题按需做一次轻量 RAG，注入上下文
    rag_context = ""
    last_user_msg = extract_last_user_message(state.get("messages"))
    if last_user_msg and agent_name in ("service", "inquiry") and _should_use_rag(last_user_msg):
        try:
            rag_context = await retrieve_knowledge(last_user_msg, intent=agent_name)
        except Exception as e:
            logger.warning(f"[Agent] RAG 检索失败: {e}")

    system_prompt = PromptBuilder.build_agent_prompt(
        agent_name=agent_name,
        cart=state.get("cart") or [],
        user_id=state.get("user_id") or 0,
        summary=state.get("summary") or "",
        user_identity=state.get("user_identity") or "",
        rag_context=rag_context,
    )
    messages = _agent_messages(state, system_prompt, agent_name)
    ctx = ToolContext(state, config)
    all_tools = build_tool_definitions(ctx)
    tools = filter_tools_for_agent(all_tools, agent_name)
    llm = get_llm(temperature=0.1).bind_tools(tools)

    # 非思考模式下限制单轮并行工具调用数量，避免无意义循环
    max_parallel_tools = 2

    added_messages: List[Any] = []
    executed_tools: set = set()  # 记录已执行过的 (name, args_json) 防止重复调用
    tool_call_count = 0

    for iteration in range(MAX_TOOL_ITERATIONS):
        response = await llm.ainvoke(messages + added_messages)

        tool_calls = _parse_tool_calls(response)
        logger.info(f"[Agent {agent_name}] LLM response, tool_calls={len(tool_calls)}")
        if not tool_calls:
            # LLM 直接回复，循环结束
            final_messages = added_messages + [response]
            update = {
                "messages": final_messages,
                "cart": ctx.cart,
                "response": response.content,
                "current_agent": agent_name,
                "metadata": {
                    **(state.get("metadata") or {}),
                    "agent": agent_name,
                    "tool_count": tool_call_count,
                },
            }
            return update

        # 处理工具调用
        added_messages.append(response)
        tcs = _parse_tool_calls(response)
        if len(tcs) > max_parallel_tools:
            tcs = tcs[:max_parallel_tools]
            logger.warning(f"[Agent {agent_name}] 单轮工具调用超过 {max_parallel_tools} 个，已截断")
        for tc in tcs:
            tool = next((t for t in tools if t.name == tc["name"]), None)
            if not tool:
                result = f"工具 {tc['name']} 不可用。"
            else:
                tool_key = (tc["name"], json.dumps(tc["args"], sort_keys=True, ensure_ascii=False))
                if tool_key in executed_tools:
                    # 同一参数重复调用，强制 LLM 基于已有结果直接回复
                    result = "该工具已经调用过并返回了结果，请直接基于结果回复用户，不要再次调用同一工具。"
                else:
                    executed_tools.add(tool_key)
                    try:
                        logger.info(f"[Agent {agent_name}] invoking tool {tc['name']} with args {tc['args']}")
                        result = await tool.ainvoke(tc["args"])
                        tool_call_count += 1
                        logger.info(f"[Agent {agent_name}] tool {tc['name']} result: {str(result)[:100]}")
                    except Exception as e:
                        logger.error(f"[Agent] 工具 {tc['name']} 调用失败: {e}")
                        result = f"调用失败：{str(e)}"

            # 识别 handoff
            if tc["name"] == "handoff_to" and isinstance(result, str) and result.startswith("[HANDOFF:"):
                target = result.split("]")[0].replace("[HANDOFF:", "").strip()
                # 防止 Agent 间踢皮球：循环检测 + 次数限制
                if target in handoff_path:
                    result = f"无法再次转交给 {target}，已出现过循环转交。请基于当前能力直接回复用户。"
                elif handoff_count >= MAX_HANDOFFS:
                    result = f"转交次数已达上限，请直接回复用户，不要再转交给其他 Agent。"
                elif target in allowed_agent_names:
                    new_path = handoff_path + [agent_name]
                    return Command(
                        goto=target,
                        update={
                            "messages": added_messages + [
                                _build_tool_result_message(tc["id"], result)
                            ],
                            "cart": ctx.cart,
                            "current_agent": target,
                            "metadata": {
                                **(state.get("metadata") or {}),
                                "agent": agent_name,
                                "handoff_to": target,
                                "handoff_path": new_path,
                                "handoff_count": handoff_count + 1,
                                "tool_count": tool_call_count,
                            },
                        },
                    )
                else:
                    result = f"无法转交给 {target}，目标 Agent 不存在。"

            added_messages.append(_build_tool_result_message(tc["id"], str(result)))

    # 达到最大迭代次数，强制收尾
    response = await llm.ainvoke(messages + added_messages)
    final_messages = added_messages + [response]
    return {
        "messages": final_messages,
        "cart": ctx.cart,
        "response": response.content,
        "current_agent": agent_name,
        "metadata": {
            **(state.get("metadata") or {}),
            "agent": agent_name,
            "tool_count": tool_call_count,
        },
    }


async def supervisor_node(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Command:
    """Supervisor：仅做轻量意图分流，随后通过 Command 交给对应 Agent。"""
    last_user_msg = extract_last_user_message(state.get("messages"))

    llm = get_llm(temperature=0.0)
    prompt = [
        SystemMessage(content=PromptBuilder.build_supervisor_prompt(last_user_msg or "你好")),
        HumanMessage(content=last_user_msg or "你好"),
    ]
    try:
        raw = await llm.ainvoke(prompt)
        content = raw.content.strip()
        # 兼容 markdown 代码块
        if content.startswith("```"):
            content = content.strip("`").strip("json").strip()
        decision = json.loads(content)
        intent = decision.get("intent", "service")
        reason = decision.get("reason", "")
    except Exception as e:
        logger.warning(f"[Supervisor] 意图解析失败，使用 service 兜底: {e}")
        intent = "service"
        reason = "解析失败，兜底到 service"

    logger.info(f"[Supervisor] intent={intent}, reason={reason}, confidence={decision.get('confidence', 'unknown')}")

    return Command(
        goto=intent,
        update={
            "intent": intent,
            "current_agent": intent,
            "metadata": {
                **(state.get("metadata") or {}),
                "supervisor_reason": reason,
            },
        },
    )


async def order_agent(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any] | Command:
    return await _run_agent_loop(state, config, "order")


async def inquiry_agent(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any] | Command:
    return await _run_agent_loop(state, config, "inquiry")


async def recommend_agent(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any] | Command:
    return await _run_agent_loop(state, config, "recommend")


async def service_agent(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any] | Command:
    return await _run_agent_loop(state, config, "service")
