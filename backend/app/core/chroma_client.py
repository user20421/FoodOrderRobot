"""
Chroma 向量数据库客户端
封装 Chroma 初始化、集合管理和文档操作
"""
import os
from typing import List, Optional
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.embeddings import ZhipuAIEmbeddings

from app.core.config import settings

_chroma_client = None
_embedding_function = None


def _get_embedding():
    """获取 Embedding 模型（懒加载）"""
    global _embedding_function
    if _embedding_function is not None:
        return _embedding_function
    api_key = settings.zhipu_api_key or os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        raise ValueError("ZHIPU_API_KEY 未设置，无法初始化 Embedding")
    _embedding_function = ZhipuAIEmbeddings(
        model=settings.embedding_model,
        api_key=api_key,
        dimensions=settings.embedding_dimensions,
    )
    return _embedding_function


class ChromaStore:
    """Chroma 向量存储管理器"""

    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self._collections: dict = {}
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        os.makedirs(self.persist_dir, exist_ok=True)
        self._initialized = True

    def get_collection(self, name: str) -> Chroma:
        """获取或创建指定集合"""
        self._ensure_initialized()
        if name not in self._collections:
            self._collections[name] = Chroma(
                collection_name=name,
                persist_directory=self.persist_dir,
                embedding_function=_get_embedding(),
            )
        return self._collections[name]

    def create_collection(self, name: str, documents: List[Document] = None) -> Chroma:
        """创建集合并可选导入文档"""
        self._ensure_initialized()
        if documents:
            collection = Chroma.from_documents(
                documents=documents,
                embedding=_get_embedding(),
                collection_name=name,
                persist_directory=self.persist_dir,
            )
        else:
            collection = Chroma(
                collection_name=name,
                persist_directory=self.persist_dir,
                embedding_function=_get_embedding(),
            )
        self._collections[name] = collection
        return collection

    def delete_collection(self, name: str):
        """删除集合"""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.persist_dir)
            client.delete_collection(name)
            if name in self._collections:
                del self._collections[name]
        except Exception as e:
            print(f"[Chroma] 删除集合失败: {e}")

    def search(self, collection_name: str, query: str, k: int = 5, filter_dict: dict = None) -> List[tuple]:
        """
        向量搜索
        返回: [(Document, score), ...]
        """
        collection = self.get_collection(collection_name)
        return collection.similarity_search_with_score(query, k=k, filter=filter_dict)

    def add_documents(self, collection_name: str, documents: List[Document]):
        """向集合中添加文档"""
        collection = self.get_collection(collection_name)
        collection.add_documents(documents)

    def is_available(self) -> bool:
        """检查 Chroma 是否可用"""
        try:
            _get_embedding()
            return True
        except Exception:
            return False


# 全局 Chroma 实例
chroma_store = ChromaStore()
