"""
记忆管理器门面
整合短期记忆、摘要记忆、向量记忆（已移除实体/用户画像记忆）
"""
from typing import List, Dict, Any, Tuple, Optional
import json

from app.ai.memory.buffer_memory import BufferMemory
from app.ai.memory.summary_memory import SummaryMemory
from app.ai.memory.vector_memory import VectorMemory
from app.core.mongodb import is_mongodb_available, is_beanie_initialized
from app.core.redis import get_redis, is_redis_available
from app.core.config import settings
from app.core.logging_config import get_logger
from app.documents.chat import ChatMessageDocument

logger = get_logger(__name__)


def _history_key(user_id: int, session_id: str) -> str:
    return f"memory:history:{user_id}:{session_id}"


def _summary_key(user_id: int, session_id: str) -> str:
    return f"memory:summary:{user_id}:{session_id}"


class MemoryManager:
    """统一记忆管理器（Buffer + Summary + Vector，移除用户画像/实体记忆）"""

    def __init__(self):
        self.buffer = BufferMemory()
        self.summary = SummaryMemory()
        self.vector = VectorMemory()

    async def _load_history_from_cache(self, user_id: int, session_id: str) -> Optional[List[Dict[str, str]]]:
        """从 Redis 读取历史对话缓存"""
        if not is_redis_available():
            return None
        try:
            redis_client = get_redis()
            key = _history_key(user_id, session_id)
            raw = await redis_client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"[MemoryManager] Redis 读取历史失败: {e}")
        return None

    async def _save_history_to_cache(self, user_id: int, session_id: str, messages: List[Dict[str, str]]):
        """将历史对话写入 Redis 缓存"""
        if not is_redis_available():
            return
        try:
            redis_client = get_redis()
            key = _history_key(user_id, session_id)
            await redis_client.set(key, json.dumps(messages, default=str), ex=86400)
        except Exception as e:
            logger.warning(f"[MemoryManager] Redis 写入历史失败: {e}")

    async def _load_history_from_mongodb(self, user_id: int, session_id: str) -> Optional[List[Dict[str, str]]]:
        """从 MongoDB 主存读取历史对话"""
        if not is_mongodb_available() or not is_beanie_initialized():
            return None
        try:
            docs = await ChatMessageDocument.find(
                ChatMessageDocument.user_id == user_id,
                ChatMessageDocument.session_id == session_id,
            ).sort(+ChatMessageDocument.created_at).limit(50).to_list()
            return [
                {
                    "role": d.role,
                    "content": d.message,
                }
                for d in docs
            ]
        except Exception as e:
            logger.warning(f"[MemoryManager] MongoDB 加载失败: {e}")
            return None

    async def _load_summary_from_cache(self, user_id: int, session_id: str) -> Optional[str]:
        """从 Redis 读取摘要缓存"""
        if not is_redis_available():
            return None
        try:
            redis_client = get_redis()
            key = _summary_key(user_id, session_id)
            raw = await redis_client.get(key)
            if raw is not None:
                return raw
        except Exception as e:
            logger.warning(f"[MemoryManager] Redis 读取摘要失败: {e}")
        return None

    async def _save_summary_to_cache(self, user_id: int, session_id: str, summary: str):
        """将摘要写入 Redis 缓存"""
        if not is_redis_available():
            return
        try:
            redis_client = get_redis()
            key = _summary_key(user_id, session_id)
            await redis_client.set(key, summary, ex=86400)
        except Exception as e:
            logger.warning(f"[MemoryManager] Redis 写入摘要失败: {e}")

    async def get_conversation_context(
        self,
        user_id: int,
        session_id: str = "default",
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        获取适合注入Agent的对话上下文
        返回: (历史消息列表, 摘要文本)
        """
        # 1. 优先从 Redis 缓存读取历史，未命中再读 MongoDB 主存
        messages = await self._load_history_from_cache(user_id, session_id)
        if messages is None:
            messages = await self._load_history_from_mongodb(user_id, session_id)
            if messages is None:
                messages = self.buffer.get(user_id)
            await self._save_history_to_cache(user_id, session_id, messages)

        # 2. Token预算裁剪 + 摘要触发
        tokens = self.buffer.estimate_tokens(messages)
        message_count = len(messages)
        summary_text = ""

        # 触发摘要的条件：消息数达到阈值 或 Token 超过上限
        should_summarize = (
            message_count >= settings.memory_summary_trigger_pairs * 2
            or tokens > settings.memory_max_tokens
        )

        if should_summarize and message_count > settings.memory_buffer_size * 2:
            # 需要裁剪和摘要
            retain_count = settings.memory_buffer_size * 2
            old_messages = messages[:-retain_count]
            recent_messages = messages[-retain_count:]

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
                    await self._save_summary_to_cache(user_id, session_id, new_summary)
                    summary_text = new_summary

            messages = recent_messages

        # 如果没有做过摘要，尝试读取已有摘要（先缓存后 MongoDB）
        if not summary_text:
            summary_text = await self._load_summary_from_cache(user_id, session_id)
        if not summary_text:
            summary_text = await self.summary.get_summary(user_id, session_id)
            if summary_text:
                await self._save_summary_to_cache(user_id, session_id, summary_text)

        return messages, summary_text

    def add_to_buffer(self, user_id: int, role: str, content: str):
        """添加消息到缓冲区"""
        self.buffer.add(user_id, role, content)

    def invalidate_cache(self, user_id: int):
        """使缓存失效（当前 Buffer 为内存，无需显式失效）"""
        pass
