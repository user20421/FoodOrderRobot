"""
系统提示词模板（基于 Markdown）
提供 PromptBuilder 用于从 backend/prompts/ 目录加载并渲染提示词。
"""
from typing import Any, Dict, List, Optional

from app.core.content_loader import load_prompt


def build_dynamic_context(
    cart: List[Dict[str, Any]],
    user_id: int,
    summary: str = "",
    user_identity: str = "",
    rag_context: str = "",
) -> str:
    """构建动态上下文信息"""
    parts = []

    if cart:
        total = 0.0
        lines = []
        for c in cart:
            unit_price = float(c.get("unit_price") or 0)
            quantity = int(c.get("quantity", 1))
            subtotal = unit_price * quantity
            total += subtotal
            lines.append(f"  {c.get('name', '未知菜品')} x{quantity} = {subtotal:.0f}元")
        parts.append(f"## 当前购物车（合计 {total:.0f} 元）\n" + "\n".join(lines))
    else:
        parts.append("## 当前购物车\n购物车为空")

    if user_identity:
        parts.append(user_identity)

    if summary:
        parts.append(f"## 对话摘要\n{summary}")

    if rag_context:
        parts.append(f"## 相关知识\n{rag_context}")

    return "\n\n".join(parts)


class PromptBuilder:
    """基于 Markdown 模板的提示词构建器"""

    @staticmethod
    def load_prompt(name: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """直接加载并渲染提示词模板"""
        return load_prompt(name, variables)

    @staticmethod
    def build_supervisor_prompt(user_message: str) -> str:
        """构建 Supervisor 系统提示词"""
        return load_prompt("supervisor", {"user_message": user_message})

    @staticmethod
    def build_agent_prompt(
        agent_name: str,
        cart: List[Dict[str, Any]],
        user_id: int,
        summary: str = "",
        user_identity: str = "",
        rag_context: str = "",
    ) -> str:
        """构建指定 Agent 的系统提示词"""
        dynamic_context = build_dynamic_context(
            cart=cart,
            user_id=user_id,
            summary=summary,
            user_identity=user_identity,
            rag_context=rag_context,
        )
        return load_prompt(
            f"agents/{agent_name}",
            {
                "dynamic_context": dynamic_context,
                "user_id": user_id,
                "summary": summary,
                "user_identity": user_identity,
                "rag_context": rag_context,
            },
        )

    @staticmethod
    def build_greeting_prompt(
        user_message: str,
        user_identity: str = "",
        summary: str = "",
    ) -> str:
        """构建直接问候提示词"""
        dynamic_context = build_dynamic_context(
            cart=[], user_id=0, summary=summary, user_identity=user_identity
        )
        return load_prompt(
            "services/greeting",
            {
                "user_message": user_message,
                "dynamic_context": dynamic_context,
                "user_identity": user_identity,
                "summary": summary,
            },
        )

    @staticmethod
    def build_image_search_prompt(description: str, menu_text: str) -> str:
        """构建图片搜菜匹配提示词"""
        return load_prompt(
            "services/image_search",
            {"description": description, "menu_text": menu_text},
        )

    @staticmethod
    def build_summary_prompt(dialogue_text: str, previous_summary: str = "") -> str:
        """构建对话摘要提示词"""
        previous_section = ""
        if previous_summary:
            previous_section = f"## 此前摘要\n{previous_summary}"
        return load_prompt(
            "services/summary",
            {
                "dialogue_text": dialogue_text,
                "previous_summary": previous_section,
            },
        )

    @staticmethod
    def build_vision_prompt() -> str:
        """构建菜品图片描述提示词"""
        return load_prompt("services/vision")


# 保持旧接口兼容：导出原始常量名（实际调用 PromptBuilder）
# 这样旧 import 语句在重构期间不会立即报错，但建议逐步改为 PromptBuilder。
SUPERVISOR_SYSTEM_PROMPT = PromptBuilder.build_supervisor_prompt("")
ORDER_AGENT_SYSTEM_PROMPT = PromptBuilder.build_agent_prompt("order", [], 0)
INQUIRY_AGENT_SYSTEM_PROMPT = PromptBuilder.build_agent_prompt("inquiry", [], 0)
RECOMMEND_AGENT_SYSTEM_PROMPT = PromptBuilder.build_agent_prompt("recommend", [], 0)
SERVICE_AGENT_SYSTEM_PROMPT = PromptBuilder.build_agent_prompt("service", [], 0)
