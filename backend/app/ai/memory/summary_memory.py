"""
摘要记忆
长对话的滚动摘要，存储在MongoDB中
"""
from typing import Optional
from langchain_core.messages import HumanMessage

from app.ai.llm import get_llm
from app.core.mongodb import get_mongodb_db, is_mongodb_available
from app.core.logging_config import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class SummaryMemory:
    """对话摘要记忆"""

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0.1)
        return self._llm

    async def save_summary(self, user_id: int, summary: str, session_id: str = "default"):
        """保存对话摘要"""
        if not is_mongodb_available():
            return
        try:
            db = get_mongodb_db()
            await db.conversation_summaries.update_one(
                {"user_id": user_id, "session_id": session_id},
                {
                    "$set": {"summary": summary, "updated_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc)},
                    "$setOnInsert": {"user_id": user_id, "session_id": session_id, "created_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc)},
                },
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[SummaryMemory] 保存摘要失败: {e}")

    async def get_summary(self, user_id: int, session_id: str = "default") -> str:
        """获取对话摘要"""
        if not is_mongodb_available():
            return ""
        try:
            db = get_mongodb_db()
            doc = await db.conversation_summaries.find_one(
                {"user_id": user_id, "session_id": session_id}
            )
            return doc.get("summary", "") if doc else ""
        except Exception as e:
            logger.warning(f"[SummaryMemory] 读取摘要失败: {e}")
            return ""

    async def generate_summary(self, dialogue_text: str, previous_summary: str = "") -> str:
        """使用LLM生成对话摘要"""
        try:
            llm = self._get_llm()
            prompt = (
                "请对以下客服对话进行简短总结，保留用户的关键意图、已确认的信息和未完成的请求。\n"
                "总结要简洁，不超过150字，不要包含格式标记。\n\n"
            )
            if previous_summary:
                prompt += f"【此前摘要】\n{previous_summary}\n\n"
            prompt += f"【新对话】\n{dialogue_text}\n\n【总结】"

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.warning(f"[SummaryMemory] 生成摘要失败: {e}")
            return ""
