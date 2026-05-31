"""
RAG 混合检索器
Dense Retrieval + Sparse Retrieval (BM25) + Metadata Filter
"""
from typing import List, Tuple, Dict, Any
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.core.chroma_client import chroma_store
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class HybridRetriever:
    """混合检索器：向量检索 + BM25 + 元数据过滤"""

    def __init__(self):
        self._bm25_index: Dict[str, BM25Okapi] = {}
        self._bm25_docs: Dict[str, List[Document]] = {}

    def _build_bm25(self, collection_name: str) -> BM25Okapi:
        """构建BM25索引"""
        if collection_name in self._bm25_index:
            return self._bm25_index[collection_name]

        try:
            collection = chroma_store.get_collection(collection_name)
            # 获取所有文档
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

        # 取top-k
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
            # Chroma返回的是(distance)，distance越小越相似，需要转换
            docs = []
            for doc, score in results:
                # 将distance转为相似度分数（简单取反）
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
        # 向量检索
        vector_results = self._vector_search(collection_name, query, k=k * 2, filter_dict=filter_dict)

        if not use_hybrid:
            return vector_results[:k]

        # BM25检索
        bm25_results = self._bm25_search(collection_name, query, k=k * 2)

        # RRF融合
        return self._rrf_fusion(vector_results, bm25_results, top_k=k)

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

        # 向量检索打分（按rank）
        for rank, (doc, _) in enumerate(vector_results):
            key = doc.page_content[:100]  # 用内容前100字作为key
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        # BM25打分（按rank）
        for rank, (doc, _) in enumerate(bm25_results):
            key = doc.page_content[:100]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        # 排序取top
        sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        results = []
        for key in sorted_keys[:top_k]:
            results.append((doc_map[key], scores[key]))
        return results


# 全局检索器
hybrid_retriever = HybridRetriever()
