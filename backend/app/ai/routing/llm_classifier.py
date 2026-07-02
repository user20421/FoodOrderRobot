"""
轻量 LLM 分类器（Layer 2 路由）

对未命中规则快速通道的消息，使用不绑定工具的直接 LLM 调用进行意图分类。
适用于问候、闲聊、简单 FAQ 等不需要工具调用的场景。
"""
import json
import re
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.agents.prompts import PromptBuilder
from app.ai.llm import get_llm
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# 简单问候 pattern，命中时跳过 LLM 直接回复
_GREETING_PATTERN = re.compile(
    r"^[\s]*(?:"
    r"(?:你|您)好[吗呀]?|"
    r"你好啊|您好啊|"
    r"hello|hi|hey|"
    r"(?:早上|上午|中午|下午|晚上)好|"
    r"(?:在吗|在么|在不在)|"
    r"(?:有人吗)|"
    r"(?:吃了吗)|"
    r"(?:帮助|help)|"
    r"(?:介绍一下)|"
    r"(?:能做什么)|"
    r"(?:有什么可以帮您)"
    r")[\s\\.!?。！？]*$",
    re.IGNORECASE,
)


async def classify_message(
    message: str,
    history_summary: str = "",
) -> Optional[Dict[str, Any]]:
    """
    使用轻量 LLM 判断消息是否需要工具处理。

    Returns:
        {"route": "greeting|faq_direct|agent", "answer": "..."} or None
    """
    text = message.strip()
    if not text:
        return None

    # 纯问候直接走 greeting，不调用 LLM
    if _GREETING_PATTERN.match(text):
        return {"route": "greeting", "answer": ""}

    system_prompt = PromptBuilder.load_prompt("services/classifier")

    context = ""
    if history_summary:
        context = f"\n\n【对话摘要】\n{history_summary}"

    try:
        llm = get_llm(temperature=0.0)
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"【用户消息】\n{text}{context}"),
        ])

        content = response.content.strip()
        if content.startswith("```"):
            content = content.strip("`").strip("json").strip()

        decision = json.loads(content)
        route = decision.get("route", "agent")

        if route in ("greeting", "faq_direct"):
            logger.info(f"[LLMClassifier] route={route}, reason={decision.get('reason', '')}")
            return {"route": route, "answer": ""}

        return None

    except Exception as e:
        logger.warning(f"[LLMClassifier] 分类失败，降级到 Agent: {e}")
        return None


async def generate_direct_reply(
    message: str,
    user_identity: str = "",
    history_summary: str = "",
) -> str:
    """
    对 greeting/faq_direct 类消息直接生成回复，不调用工具。
    """
    from app.ai.agents.prompts import PromptBuilder

    system_prompt = PromptBuilder.build_greeting_prompt(
        user_message=message,
        user_identity=user_identity,
        summary=history_summary,
    )

    try:
        llm = get_llm(temperature=0.5)
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=message.strip()),
        ])
        return response.content.strip()
    except Exception as e:
        logger.warning(f"[LLMClassifier] 直接回复生成失败: {e}")
        return "您好，有什么可以帮您的吗？"
