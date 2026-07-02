"""
RAG 文档索引器
负责构建和更新 Chroma 向量索引
"""
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.chroma_client import chroma_store
from app.core.logging_config import get_logger
from app.core.content_loader import (
    build_menu_documents as _build_menu_documents,
    build_faq_documents as _build_faq_documents,
    build_store_documents as _build_store_documents,
)

logger = get_logger(__name__)


def _split_documents(docs: List[Document]) -> List[Document]:
    """智能分块"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", "；", " ", ""],
    )
    split_docs = splitter.split_documents(docs)
    # 赋予唯一ID
    for i, d in enumerate(split_docs):
        d.metadata["chunk_id"] = i
    return split_docs


class RAGIndexer:
    """RAG 索引管理器"""

    COLLECTIONS = {
        "menu": "menu_docs",
        "faq": "faq_docs",
        "store": "store_docs",
    }

    def __init__(self):
        self._initialized = False

    def initialize(self, force_rebuild: bool = False):
        """初始化所有索引"""
        if self._initialized and not force_rebuild:
            return

        if not chroma_store.is_available():
            logger.warning("Chroma 不可用，跳过索引初始化")
            return

        try:
            # 小批量导入，避免单次 Embedding 请求过大被服务端拒绝
            batch_size = 16

            # 菜单索引
            menu_docs = _build_menu_documents()
            if force_rebuild:
                chroma_store.delete_collection(self.COLLECTIONS["menu"])
            self._create_collection_batched(self.COLLECTIONS["menu"], menu_docs, batch_size)
            logger.info(f"[RAG] 菜单索引完成: {len(menu_docs)} 条")

            # FAQ索引
            faq_docs = _build_faq_documents()
            if force_rebuild:
                chroma_store.delete_collection(self.COLLECTIONS["faq"])
            self._create_collection_batched(self.COLLECTIONS["faq"], faq_docs, batch_size)
            logger.info(f"[RAG] FAQ索引完成: {len(faq_docs)} 条")

            # 店铺文档索引
            store_docs = _build_store_documents()
            if force_rebuild:
                chroma_store.delete_collection(self.COLLECTIONS["store"])
            self._create_collection_batched(self.COLLECTIONS["store"], store_docs, batch_size)
            logger.info(f"[RAG] 店铺文档索引完成: {len(store_docs)} 条")

            self._initialized = True
            logger.info("[RAG] 所有索引初始化完成")

        except Exception as e:
            logger.error(f"[RAG] 索引初始化失败: {e}")
            raise

    def _create_collection_batched(self, name: str, documents: List[Document], batch_size: int = 16):
        """分批创建集合并导入文档"""
        if not documents:
            chroma_store.create_collection(name)
            return

        # 先创建集合并导入第一批
        first_batch = documents[:batch_size]
        collection = chroma_store.create_collection(name, first_batch)

        # 后续分批添加
        for i in range(batch_size, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            try:
                collection.add_documents(batch)
            except Exception as e:
                logger.warning(f"[RAG] {name} 第 {i // batch_size + 1} 批导入失败: {e}")
                # 继续处理后续批次，不要中断整个索引流程
                continue


# 全局索引器
rag_indexer = RAGIndexer()
