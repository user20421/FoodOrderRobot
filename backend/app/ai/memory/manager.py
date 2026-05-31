"""
记忆管理器门面
整合短期记忆、摘要记忆、实体记忆、向量记忆
"""
from typing import List, Dict, Any, Tuple

from app.ai.memory.buffer_memory import BufferMemory
from app.ai.memory.summary_memory import SummaryMemory
from app.ai.memory.entity_memory import EntityMemory
from app.ai.memory.vector_memory import VectorMemory
from app.core.mongodb import is_mongodb_available
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """统一记忆管理器"""

    def __init__(self):
        self.buffer = BufferMemory()
        self.summary = SummaryMemory()
        self.entity = EntityMemory()
        self.vector = VectorMemory()

    async def get_conversation_context(
        self,
        user_id: int,
        session_id: str = "default",
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        获取适合注入Agent的对话上下文
        返回: (历史消息列表, 摘要文本)
        """
        # 1. 从MongoDB加载完整历史（如果可用）
        if is_mongodb_available():
            try:
                from app.core.mongodb import get_mongodb_db
                db = get_mongodb_db()
                cursor = db.chat_messages.find(
                    {"user_id": user_id, "session_id": session_id}
                ).sort("created_at", 1).limit(50)
                records = await cursor.to_list(length=50)
                messages = []
                for r in records:
                    messages.append({
                        "role": r.get("role"),
                        "content": r.get("message", ""),
                    })
            except Exception as e:
                logger.warning(f"[MemoryManager] MongoDB加载失败: {e}")
                messages = self.buffer.get(user_id)
        else:
            messages = self.buffer.get(user_id)

        # 2. Token预算裁剪
        tokens = self.buffer.estimate_tokens(messages)
        summary_text = ""

        if tokens > settings.memory_max_tokens:
            # 需要裁剪和摘要
            retain_count = settings.memory_buffer_size * 2
            old_messages = messages[:-retain_count] if len(messages) > retain_count else []
            recent_messages = messages[-retain_count:] if len(messages) > retain_count else messages

            if old_messages:
                dialogue_text = "\n".join([
                    f"{'用户' if m['role'] == 'user' else '机器人'}：{m['content']}"
                    for m in old_messages
                ])
                # 获取现有摘要
                existing_summary = await self.summary.get_summary(user_id, session_id)
                new_summary = await self.summary.generate_summary(dialogue_text, existing_summary)
                if new_summary:
                    await self.summary.save_summary(user_id, new_summary, session_id)
                    summary_text = new_summary

            messages = recent_messages

        # 如果没有做过摘要，尝试读取已有摘要
        if not summary_text:
            summary_text = await self.summary.get_summary(user_id, session_id)

        return messages, summary_text

    async def get_user_profile_text(self, user_id: int) -> str:
        """获取用户画像文本（用于提示词注入）"""
        profile = await self.entity.get_profile(user_id)
        return self.entity.format_profile_for_prompt(profile)

    async def search_similar_memories(self, user_id: int, query: str, k: int = 3) -> List[str]:
        """搜索相似历史记忆"""
        return await self.vector.search_similar(user_id, query, k)

    def add_to_buffer(self, user_id: int, role: str, content: str):
        """添加消息到缓冲区"""
        self.buffer.add(user_id, role, content)

    def invalidate_cache(self, user_id: int):
        """使缓存失效"""
        # Buffer不需要显式失效，每次get都取最新
        pass
