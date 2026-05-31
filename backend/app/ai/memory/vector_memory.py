"""
向量记忆
将历史对话向量化存储，支持语义检索相似历史
"""
from typing import List, Dict, Any
from datetime import datetime, timezone

from langchain_core.documents import Document

from app.ai.llm import get_embedding
from app.core.chroma_client import chroma_store
from app.core.mongodb import get_mongodb_db, is_mongodb_available
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class VectorMemory:
    """向量语义记忆"""

    COLLECTION_NAME = "conversation_docs"

    async def add_conversation(self, user_id: int, role: str, content: str):
        """添加对话到向量记忆"""
        try:
            doc = Document(
                page_content=f"{'用户' if role == 'user' else '机器人'}：{content}",
                metadata={
                    "user_id": user_id,
                    "role": role,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            chroma_store.add_documents(self.COLLECTION_NAME, [doc])
        except Exception as e:
            logger.warning(f"[VectorMemory] 添加向量记忆失败: {e}")

    async def search_similar(
        self,
        user_id: int,
        query: str,
        k: int = 3,
    ) -> List[str]:
        """
        检索与用户查询语义相似的历史对话
        返回: [对话文本, ...]
        """
        try:
            results = chroma_store.search(
                self.COLLECTION_NAME,
                query,
                k=k * 2,
            )
            # 过滤当前用户的对话
            filtered = []
            for doc, score in results:
                if doc.metadata.get("user_id") == user_id:
                    filtered.append(doc.page_content)
            return filtered[:k]
        except Exception as e:
            logger.warning(f"[VectorMemory] 语义检索失败: {e}")
            return []
