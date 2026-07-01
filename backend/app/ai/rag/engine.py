"""
RAG 引擎门面（轻量版）。
仅保留混合检索，移除查询重写、多查询扩展、LLM 重排序和上下文压缩。
"""
from typing import List, Dict, Any, Optional

from app.ai.rag.retriever import retrieve_knowledge
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RAGEngine:
    """轻量 RAG 引擎"""

    async def query(
        self,
        question: str,
        history: List[Dict[str, str]] = None,
        k: int = None,
        use_multi_query: bool = False,
        use_rerank: bool = False,
    ) -> str:
        """
        执行 RAG 查询，返回检索到的上下文文本。
        history / use_multi_query / use_rerank / k 参数保留仅用于向后兼容，
        实际均走单查询轻量混合检索。
        """
        try:
            return await retrieve_knowledge(question)
        except Exception as e:
            logger.error(f"[RAG] 查询失败: {e}")
            return ""


# 全局 RAG 引擎
rag_engine = RAGEngine()
