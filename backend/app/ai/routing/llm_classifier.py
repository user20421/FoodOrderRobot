"""
轻量 LLM 分类器（Layer 2 路由）

对未命中规则快速通道的消息，使用不绑定工具的直接 LLM 调用进行意图分类。
适用于问候、闲聊、简单 FAQ 等不需要工具调用的场景。

注意：纯问候已在 fast_router 中通过模板直接返回；本模块主要作为快速通道未覆盖
的 greeting/faq_direct 补充，以及 Agent 路由兜底。
"""
import json
import re
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.agents.prompts import PromptBuilder
from app.ai.llm import get_llm
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# 简单问候 pattern，命中时跳过 LLM 直接返回模板答案
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
    r"(?:你是谁)|"
    r"(?:你是什么)|"
    r"(?:你是哪个)|"
    r"(?:有什么可以帮您)|"
    r"(?:您好)"
    r")[\s\\.!?。！？]*$",
    re.IGNORECASE,
)


def _greeting_reply(message: str) -> str:
    """根据问候内容返回对应的内置模板回复。"""
    text = message.strip().lower()
    if re.search(r"谁|什么|哪个", text):
        return "您好，我是美味餐厅的智能点餐助手小餐，可以帮您点餐、查菜单、管理购物车和解答常见问题。请问今天想吃点什么？"
    if re.search(r"帮助|help|能做什么|介绍一下", text):
        return "您好！我可以帮您：\n• 点餐加菜、修改购物车\n• 查看菜单、推荐菜品\n• 查询订单、营业时间、配送等常见问题\n请问今天想吃点什么？"
    return "您好！欢迎来到美味餐厅，我是您的智能点餐助手小餐。请问今天想吃点什么？"


async def classify_message(
    message: str,
    history_summary: str = "",
) -> Optional[Dict[str, Any]]:
    """
    使用轻量 LLM 判断消息是否需要工具处理。

    Returns:
        {"route": "greeting|faq_direct|agent|too_complex", "answer": "..."} or None
        - route=greeting 时，answer 为可直接返回的模板回复。
        - route=faq_direct 时，answer 为空，由调用方生成回复。
        - route=too_complex 时，answer 为固定兜底回复。
        - route=agent 时，返回 None，让上层继续走 Agent 图。
    """
    text = message.strip()
    if not text:
        return None

    # 纯问候直接返回模板，不调用 LLM
    if _GREETING_PATTERN.match(text):
        return {"route": "greeting", "answer": _greeting_reply(text)}

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

        if route == "greeting":
            return {"route": "greeting", "answer": _greeting_reply(text)}
        if route == "faq_direct":
            logger.info(f"[LLMClassifier] route={route}, reason={decision.get('reason', '')}")
            return {"route": "faq_direct", "answer": ""}
        if route == "too_complex":
            logger.info(f"[LLMClassifier] route={route}, reason={decision.get('reason', '')}")
            return {
                "route": "too_complex",
                "answer": "抱歉，我没有完全听懂您的问题。您可以换个方式告诉我，比如：'来一份宫保鸡丁'、'查看菜单'或'我的订单'。",
            }

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
    - greeting：使用内置问候模板
    - faq_direct：先检索 RAG 知识库，再基于检索结果生成回复，避免幻觉
    """
    from app.ai.agents.prompts import PromptBuilder
    from app.ai.rag.retriever import retrieve_knowledge

    text = message.strip()

    system_prompt = PromptBuilder.build_greeting_prompt(
        user_message=text,
        user_identity=user_identity,
        summary=history_summary,
    )

    # FAQ 类问题先检索知识库，把参考资料注入 system prompt
    if not _GREETING_PATTERN.match(text):
        try:
            rag_context = await retrieve_knowledge(text, intent="service")
            if rag_context and rag_context != "未找到相关知识。":
                system_prompt += (
                    f"\n\n【参考资料】\n{rag_context}\n\n"
                    "请基于以上参考资料回答用户问题。如果参考资料中没有相关信息，请诚实说明，不要编造。"
                )
            else:
                system_prompt += (
                    "\n\n【系统提示】\n"
                    "该问题未在餐厅知识库中找到直接答案。如果问题是轻松的日常闲聊或通用知识，你可以简短回答，"
                    "但请在回复最后自然引导用户回到点餐场景；如果问题涉及具体的餐厅业务但资料不足，请诚实说明。"
                )
        except Exception as e:
            logger.warning(f"[LLMClassifier] FAQ 检索失败，继续直接生成: {e}")

    try:
        llm = get_llm(temperature=0.5)
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=text),
        ])
        return response.content.strip()
    except Exception as e:
        logger.warning(f"[LLMClassifier] 直接回复生成失败: {e}")
        return "您好，有什么可以帮您的吗？"
