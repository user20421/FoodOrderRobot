"""
RAG 重排序器
LLM-based 重排序 + 上下文压缩
"""
import re
from typing import List, Tuple
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from app.ai.llm import get_llm
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class LLMReranker:
    """基于LLM的重排序器"""

    async def rerank(
        self,
        query: str,
        docs: List[Tuple[Document, float]],
        top_n: int = 3,
    ) -> List[Document]:
        """
        使用LLM对文档进行重排序
        返回Top-N最相关的文档
        """
        if len(docs) <= top_n:
            return [d for d, _ in docs]

        try:
            llm = get_llm(temperature=0.1)

            # 准备文档片段
            doc_texts = []
            for i, (doc, _) in enumerate(docs):
                text = doc.page_content[:300].replace("\n", " ")
                doc_texts.append(f"[{i+1}] {text}")

            doc_section = "\n".join(doc_texts)
            prompt = (
                f"问题：{query}\n\n"
                f"以下是若干相关文档片段，请按与问题的相关性从高到低排序。\n"
                f"只输出编号列表，用逗号分隔，最相关的在前。\n\n"
                f"{doc_section}\n\n"
                f"相关性排序（最相关在前）："
            )

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            text = response.content.strip()

            # 解析编号
            numbers = re.findall(r"\d+", text)
            ranked = []
            for n in numbers:
                idx = int(n) - 1
                if 0 <= idx < len(docs):
                    doc = docs[idx][0]
                    if doc not in ranked:
                        ranked.append(doc)

            # 补充未排序的文档
            for doc, _ in docs:
                if doc not in ranked:
                    ranked.append(doc)

            return ranked[:top_n]

        except KeyError as e:
            if str(e) == "'request'":
                logger.warning("[Reranker] 大模型服务不可用，跳过重排序")
            else:
                logger.warning(f"[Reranker] KeyError: {e}")
            return [d for d, _ in docs[:top_n]]
        except Exception as e:
            logger.warning(f"[Reranker] LLM重排序失败: {e}")
            return [d for d, _ in docs[:top_n]]


class ContextCompressor:
    """上下文压缩器：提取文档中最相关的句子"""

    def compress_sync(
        self,
        query: str,
        docs: List[Document],
        max_length: int = 800,
    ) -> str:
        """
        压缩上下文到指定长度
        策略：保留开头段落，超出时截断
        """
        contexts = []
        total_length = 0

        for i, doc in enumerate(docs, 1):
            text = doc.page_content
            if total_length + len(text) > max_length and contexts:
                # 截断最后一段
                remaining = max_length - total_length
                if remaining > 50:
                    contexts.append(f"[相关文档 {i}]\n{text[:remaining]}...")
                break
            contexts.append(f"[相关文档 {i}]\n{text}")
            total_length += len(text) + 20

        return "\n\n".join(contexts)

    async def compress(
        self,
        query: str,
        docs: List[Document],
        max_length: int = 800,
    ) -> str:
        """向后兼容的异步包装"""
        return self.compress_sync(query, docs, max_length)


# 全局实例
llm_reranker = LLMReranker()
context_compressor = ContextCompressor()
