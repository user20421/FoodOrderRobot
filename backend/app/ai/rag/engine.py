"""
RAG 引擎门面
整合 Query Rewriting → Multi-Query → Hybrid Retrieval → RRF → Rerank → Compression
"""
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage

from app.ai.llm import get_llm
from app.ai.rag.retriever import hybrid_retriever
from app.ai.rag.reranker import llm_reranker, context_compressor
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RAGEngine:
    """高级RAG引擎"""

    COLLECTIONS = ["menu_docs", "faq_docs", "store_docs"]

    async def query(
        self,
        question: str,
        history: List[Dict[str, str]] = None,
        k: int = None,
        use_multi_query: bool = True,
        use_rerank: bool = True,
    ) -> str:
        """
        执行RAG查询
        返回检索到的上下文文本
        """
        k = k or settings.rag_top_k

        try:
            # 1. Query Rewriting（查询重写）
            rewritten = await self._rewrite_query(question, history)
            if rewritten != question:
                logger.info(f"[RAG] Query重写: '{question}' -> '{rewritten}'")

            # 2. Multi-Query Expansion（多查询扩展）
            queries = [rewritten]
            if use_multi_query:
                expanded = await self._expand_queries(rewritten)
                queries.extend(expanded)

            # 3. Hybrid Retrieval（混合检索）
            all_results = []
            for collection in self.COLLECTIONS:
                for q in queries:
                    results = hybrid_retriever.search(collection, q, k=k * 2)
                    all_results.extend(results)

            # 去重（按内容前100字）
            seen = set()
            unique_results = []
            for doc, score in all_results:
                key = doc.page_content[:100]
                if key not in seen:
                    seen.add(key)
                    unique_results.append((doc, score))

            if not unique_results:
                return "未找到相关信息。"

            # 4. Rerank（重排序）
            if use_rerank and len(unique_results) > k:
                final_docs = await llm_reranker.rerank(rewritten, unique_results, top_n=k)
            else:
                final_docs = [d for d, _ in unique_results[:k]]

            # 5. Context Compression（上下文压缩）
            context = await context_compressor.compress(rewritten, final_docs)
            return context

        except KeyError as e:
            if str(e) == "'request'":
                logger.warning("[RAG] 大模型服务不可用，跳过RAG")
            else:
                logger.warning(f"[RAG] KeyError: {e}")
            return ""
        except Exception as e:
            logger.error(f"[RAG] 查询失败: {e}")
            return ""

    async def _rewrite_query(self, question: str, history: List[Dict[str, str]] = None) -> str:
        """结合对话历史重写查询"""
        if not history:
            return question

        try:
            llm = get_llm(temperature=0.1)
            history_text = ""
            if history:
                lines = []
                for h in history[-4:]:
                    role = "用户" if h.get("role") == "user" else "机器人"
                    lines.append(f"{role}: {h.get('content', '')}")
                history_text = "\n".join(lines) + "\n\n"

            prompt = (
                f"{history_text}"
                f"用户当前问题：{question}\n\n"
                f"请将用户的问题改写为一个适合用于知识库检索的简洁查询。要求：\n"
                f"1. 消除指代歧义（如'那个''这个''来一份'要还原为具体实体）\n"
                f"2. 保留核心关键词（菜品名、属性等）\n"
                f"3. 不要添加原文中没有的信息\n"
                f"4. 直接输出改写后的查询，不要解释。\n\n"
                f"改写后的查询："
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            rewritten = response.content.strip()
            if rewritten and 2 <= len(rewritten) < 200:
                return rewritten
        except Exception as e:
            logger.warning(f"[RAG] 查询重写失败: {e}")
        return question

    async def _expand_queries(self, question: str) -> List[str]:
        """多查询扩展：生成同义查询"""
        try:
            llm = get_llm(temperature=0.3)
            prompt = (
                f"原问题：{question}\n\n"
                f"请生成{settings.rag_multi_query_count}个不同角度的同义查询，用于检索相关知识。\n"
                f"要求：覆盖不同表述方式，保留核心关键词。\n"
                f"每行输出一个查询，不要编号和解释："
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            lines = [line.strip() for line in response.content.strip().split("\n") if line.strip()]
            return lines[:settings.rag_multi_query_count]
        except Exception as e:
            logger.warning(f"[RAG] 多查询扩展失败: {e}")
            return []


# 全局RAG引擎
rag_engine = RAGEngine()
