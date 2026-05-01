"""
推荐智能体 (RecommenderAgent)

职责：根据用户口味偏好、场景需求、饮食限制，从本店菜单中筛选并推荐合适的菜品。

适用场景：
  - "有什么好吃的？"
  - "推荐几个下饭菜"
  - "我想吃点清淡的"
  - "有什么辣的菜？"
  - "适合小孩吃的有什么？"

工具集：
  - search_by_preference: 按偏好筛选菜品
  - get_signature_dishes: 获取招牌菜
  - rag_retrieve: RAG 向量检索补充上下文
  - format_dish_list: 格式化推荐文案
"""
import os

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.agents.base import BaseAgent
from app.ai.tools import (
    extract_preferences,
    search_by_preference,
    get_signature_dishes,
    format_dish_list,
    get_menu_summary,
)
from app.ai.rag import query_rag
from app.core.config import settings


def _get_llm():
    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未设置")
    return ChatTongyi(
        model=settings.chat_model,
        dashscope_api_key=api_key,
        temperature=0.3,
    )


class RecommenderAgent(BaseAgent):
    """
    推荐智能体
    理解用户偏好，从菜单中筛选匹配菜品，用自然口吻推荐。
    """

    def __init__(self):
        super().__init__(
            name="推荐专员",
            description="根据用户口味偏好、场景需求推荐合适的菜品",
        )

    async def run(self, user_id: int, message: str, cart: list = None) -> dict:
        """
        推荐流程：
        1. 提取用户偏好关键词
        2. 从数据库筛选候选菜品
        3. 若 LLM 可用，用 RAG + DB 结果润色成自然口吻
        4. 否则直接返回数据库筛选结果
        """
        # Step 1: 提取偏好
        prefs = extract_preferences(message)

        # Step 2: 数据库筛选
        dishes = await search_by_preference(
            spicy_level=prefs.get("spicy_level"),
            categories=prefs.get("categories"),
            tags=prefs.get("tags"),
            dietary=prefs.get("dietary"),
        )

        # 如果没有偏好或筛选结果太少，用招牌菜兜底
        if not dishes or len(dishes) < 3:
            dishes = await get_signature_dishes(limit=5)

        db_response = format_dish_list(dishes, title="为您推荐")

        # Step 3: 尝试 LLM 润色（带防幻觉校验）
        try:
            rag_context = query_rag(message)
        except Exception:
            rag_context = ""

        try:
            llm = _get_llm()
            menu_summary = await get_menu_summary()

            system_msg = (
                "你是本店服务员小餐。请严格根据下方提供的本店菜品信息回答，"
                "只能推荐明确列出的菜品，绝对不要编造不存在的菜品名、价格或描述。"
                "回答简洁流畅，像真人服务员一样自然亲切，不要长篇大论。"
                "如果提到具体菜品，必须准确提及价格和辣度。"
                "绝对不要使用emoji、颜文字或任何特殊符号。"
            )
            human_msg = (
                f"顾客说：{message}\n\n"
                f"本店菜单概览：\n{menu_summary}\n\n"
                f"系统筛选出的推荐菜品：\n{db_response}\n\n"
                f"相关补充信息：\n{rag_context}\n\n"
                f"请基于以上信息，用自然亲切的口吻给顾客推荐菜品："
            )
            result = await llm.ainvoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=human_msg),
            ])
            llm_response = result.content.strip()

            # 防幻觉校验：LLM 回复中至少提到一个真实菜品名
            dish_names = {d.name for d in dishes}
            mentioned = any(name in llm_response for name in dish_names)
            if mentioned:
                return {"response": llm_response}
        except Exception:
            pass

        # Fallback：直接返回数据库筛选结果
        return {"response": db_response}
