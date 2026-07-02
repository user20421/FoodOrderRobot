"""
RAG 轻量检索器
Dense Retrieval + Sparse Retrieval (BM25)，支持查询改写与按意图的 metadata 过滤。
"""
import re
from typing import List, Tuple, Dict, Any, Optional
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.core.chroma_client import chroma_store
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 查询改写与意图映射
# ---------------------------------------------------------------------------

_INTENT_COLLECTION_MAP = {
    "inquiry": ["menu_docs", "faq_docs"],
    "recommend": ["menu_docs", "faq_docs"],
    "service": ["faq_docs", "store_docs"],
}

_INTENT_KEYWORDS = {
    "menu": ["菜", "鱼", "肉", "鸡", "虾", "豆腐", "辣度", "价格", "多少钱", "菜单"],
    "store": ["营业", "配送", "会员", "预订", "电话", "地址", "外卖", "优惠", "政策", "过敏"],
}


def _infer_intent(query: str) -> str:
    """根据关键词推断意图，用于选择检索集合"""
    text = query.lower()
    menu_score = sum(1 for kw in _INTENT_KEYWORDS["menu"] if kw in text)
    store_score = sum(1 for kw in _INTENT_KEYWORDS["store"] if kw in text)
    if menu_score > store_score:
        return "inquiry"
    if store_score > menu_score:
        return "service"
    return "service"


def _rewrite_query(query: str) -> str:
    """
    轻量查询改写：将口语化问题补充关键词，便于向量/BM25 检索。
    不调用 LLM，避免增加延迟。
    """
    text = query.strip()

    # 辣度相关
    if re.search(r"最辣|辣度最高|最辣的菜", text):
        return f"{text} 辣度5级 特辣"
    if re.search(r"不辣|不吃辣|微辣", text):
        return f"{text} 辣度0级 不辣 清淡"

    # 推荐相关
    if re.search(r"下饭|下饭菜", text):
        return f"{text} 推荐 下饭"
    if re.search(r"宴请|聚餐|大菜", text):
        return f"{text} 推荐 宴请 大菜"
    if re.search(r"小朋友|小孩|老人", text):
        return f"{text} 推荐 清淡 不辣"

    # 食材相关
    if re.search(r"海鲜|鱼|虾|贝|蟹", text):
        return f"{text} 海鲜"
    if re.search(r"素菜|蔬菜|清淡", text):
        return f"{text} 素菜 清淡"

    return text


# ---------------------------------------------------------------------------
# 混合检索器
# ---------------------------------------------------------------------------

class HybridRetriever:
    """混合检索器：向量检索 + BM25"""

    DEFAULT_COLLECTIONS = ["menu_docs", "faq_docs", "store_docs"]

    def __init__(self):
        self._bm25_index: Dict[str, BM25Okapi] = {}
        self._bm25_docs: Dict[str, List[Document]] = {}

    def _build_bm25(self, collection_name: str) -> Optional[BM25Okapi]:
        """构建BM25索引"""
        if collection_name in self._bm25_index:
            return self._bm25_index[collection_name]

        try:
            collection = chroma_store.get_collection(collection_name)
            all_docs = collection.get()
            documents = []
            for i, text in enumerate(all_docs.get("documents", [])):
                metadata = all_docs.get("metadatas", [{}])[i] if all_docs.get("metadatas") else {}
                documents.append(Document(page_content=text, metadata=metadata or {}))

            if not documents:
                return None

            # 按字切分（适合中文）
            tokenized = [list(d.page_content) for d in documents]
            self._bm25_docs[collection_name] = documents
            self._bm25_index[collection_name] = BM25Okapi(tokenized)
            return self._bm25_index[collection_name]
        except Exception as e:
            logger.warning(f"[Retriever] BM25构建失败: {e}")
            return None

    def _bm25_search(self, collection_name: str, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """BM25检索"""
        bm25 = self._build_bm25(collection_name)
        if bm25 is None:
            return []

        tokenized_query = list(query)
        scores = bm25.get_scores(tokenized_query)
        docs = self._bm25_docs.get(collection_name, [])

        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((docs[idx], float(scores[idx])))
        return results

    def _vector_search(self, collection_name: str, query: str, k: int = 5, filter_dict: dict = None) -> List[Tuple[Document, float]]:
        """向量检索"""
        try:
            results = chroma_store.search(collection_name, query, k=k, filter_dict=filter_dict)
            docs = []
            for doc, score in results:
                # 将 distance 转为相似度分数（简单取反）
                similarity = max(0, 1.0 - score)
                docs.append((doc, similarity))
            return docs
        except Exception as e:
            logger.warning(f"[Retriever] 向量检索失败: {e}")
            return []

    def search(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
        filter_dict: dict = None,
        use_hybrid: bool = True,
    ) -> List[Tuple[Document, float]]:
        """
        混合检索
        返回: [(Document, score), ...]
        """
        vector_results = self._vector_search(collection_name, query, k=k * 2, filter_dict=filter_dict)

        if not use_hybrid:
            return vector_results[:k]

        bm25_results = self._bm25_search(collection_name, query, k=k * 2)
        return self._rrf_fusion(vector_results, bm25_results, top_k=k)

    def search_all_collections(
        self,
        query: str,
        k: int = None,
        intent: str = None,
    ) -> List[Tuple[Document, float]]:
        """
        在所有知识库集合中检索并去重。
        根据 intent 选择优先检索的集合。
        """
        k = k or settings.rag_top_k
        intent = intent or _infer_intent(query)
        collections = _INTENT_COLLECTION_MAP.get(intent, self.DEFAULT_COLLECTIONS)

        all_results = []
        for collection in collections:
            try:
                results = self.search(collection, query, k=k)
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"[Retriever] 检索集合 {collection} 失败: {e}")

        # 去重（按内容前100字）并取 top-k
        seen = set()
        unique_results = []
        for doc, score in sorted(all_results, key=lambda x: x[1], reverse=True):
            key = doc.page_content[:100]
            if key not in seen:
                seen.add(key)
                unique_results.append((doc, score))
        return unique_results[:k]

    @staticmethod
    def _rrf_fusion(
        vector_results: List[Tuple[Document, float]],
        bm25_results: List[Tuple[Document, float]],
        top_k: int = 5,
        k: int = 60,
    ) -> List[Tuple[Document, float]]:
        """RRF (Reciprocal Rank Fusion) 融合"""
        scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        for rank, (doc, _) in enumerate(vector_results):
            key = doc.page_content[:100]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        for rank, (doc, _) in enumerate(bm25_results):
            key = doc.page_content[:100]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        results = []
        for key in sorted_keys[:top_k]:
            results.append((doc_map[key], scores[key]))
        return results


# 全局检索器
hybrid_retriever = HybridRetriever()


# ---------------------------------------------------------------------------
# RAG 入口
# ---------------------------------------------------------------------------


async def retrieve_knowledge(question: str, intent: str = None) -> str:
    """
    RAG 入口：查询改写 + 按意图选择集合 + 混合检索。
    """
    try:
        rewritten = _rewrite_query(question)
        results = hybrid_retriever.search_all_collections(rewritten, intent=intent)
        if not results:
            return "未找到相关知识。"
        lines = []
        for i, (doc, _) in enumerate(results, 1):
            lines.append(f"[{i}] {doc.page_content}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning(f"[retrieve_knowledge] 检索失败: {e}")
        return ""
