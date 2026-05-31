"""
短期缓冲记忆
内存中的滑动窗口，保存最近N轮对话
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
from collections import defaultdict

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BufferMemory:
    """短期缓冲记忆"""

    def __init__(self, max_size: int = None):
        self.max_size = max_size or settings.memory_buffer_size
        # 内存存储: {user_id: [messages]}
        self._store: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

    def add(self, user_id: int, role: str, content: str):
        """添加消息到缓冲区"""
        self._store[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # 滑动窗口
        if len(self._store[user_id]) > self.max_size * 2:
            self._store[user_id] = self._store[user_id][-self.max_size * 2:]

    def get(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的近期对话"""
        return list(self._store[user_id])

    def clear(self, user_id: int):
        """清空用户缓冲区"""
        self._store[user_id] = []

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """估算token数（中文字符数 * 1.5）"""
        total = 0
        for m in messages:
            total += int(len(m.get("content", "")) * 1.5)
        return total
