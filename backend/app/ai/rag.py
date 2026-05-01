"""
RAG 模块
使用 Chroma 向量数据库 + DashScope Embedding (text-embedding-v2)
数据来源：mock 菜单 和 FAQ
"""
import os
from typing import List

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.embeddings.dashscope import DashScopeEmbeddings
from langchain_text_splitters import CharacterTextSplitter

from app.core.config import settings
from app.mock.data import MENU_ITEMS, FAQ_DATA

# Chroma 持久化路径
CHROMA_PERSIST_DIR = "./chroma_db"


def _get_embedding():
    """获取 DashScope Embedding 实例"""
    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未设置，无法初始化 Embedding")
    return DashScopeEmbeddings(
        model=settings.embedding_model,
        dashscope_api_key=api_key,
    )


def _build_documents() -> List[Document]:
    """将菜单和 FAQ 数据构建为 LangChain Document"""
    documents: List[Document] = []

    # 菜单文档
    for item in MENU_ITEMS:
        content = (
            f"菜品名称：{item['name']}\n"
            f"描述：{item['description']}\n"
            f"价格：{item['price']}元\n"
            f"辣度：{item['spicy_level']}\n"
            f"分类：{item['category']}\n"
            f"标签：{item['tags']}"
        )
        documents.append(Document(page_content=content, metadata={"source": "menu", "name": item["name"]}))

    # FAQ 文档
    for faq in FAQ_DATA:
        content = f"问题：{faq['question']}\n回答：{faq['answer']}"
        documents.append(Document(page_content=content, metadata={"source": "faq"}))

    return documents


def _split_documents(docs: List[Document]) -> List[Document]:
    """简单的文本切分，保持段落完整"""
    splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=500,
        chunk_overlap=50,
    )
    return splitter.split_documents(docs)


class RAGStore:
    """
    RAG 向量存储封装
    首次初始化时会加载 mock 数据到 Chroma
    """

    def __init__(self):
        self._vectorstore: Chroma | None = None
        self._initialized = False

    def _init(self):
        if self._initialized:
            return

        embedding = _get_embedding()

        # 检查是否已有持久化数据
        if os.path.exists(CHROMA_PERSIST_DIR) and os.listdir(CHROMA_PERSIST_DIR):
            self._vectorstore = Chroma(
                persist_directory=CHROMA_PERSIST_DIR,
                embedding_function=embedding,
            )
        else:
            docs = _build_documents()
            split_docs = _split_documents(docs)
            self._vectorstore = Chroma.from_documents(
                documents=split_docs,
                embedding=embedding,
                persist_directory=CHROMA_PERSIST_DIR,
            )
            # Chroma 新版自动持久化，无需显式调用 persist()

        self._initialized = True

    @property
    def vectorstore(self) -> Chroma:
        self._init()
        return self._vectorstore

    def query(self, question: str, k: int = 3) -> str:
        """
        检索与问题最相关的文档内容，拼接后返回
        """
        try:
            vs = self.vectorstore
        except ValueError as e:
            return f"检索服务暂不可用：{e}"

        results = vs.similarity_search(question, k=k)
        if not results:
            return "未找到相关信息。"

        contexts = []
        for i, doc in enumerate(results, 1):
            contexts.append(f"[相关文档 {i}]\n{doc.page_content}")

        return "\n\n".join(contexts)


# 全局 RAG 实例
_rag_store = RAGStore()


def query_rag(question: str) -> str:
    """
    对外提供的 RAG 查询接口
    输入问题，返回检索到的相关文本
    """
    return _rag_store.query(question)


if __name__ == "__main__":
    # 本地测试
    print(query_rag("有什么辣的菜"))
