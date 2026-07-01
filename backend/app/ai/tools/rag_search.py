"""
知识库检索工具。
"""
from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.ai.rag.retriever import retrieve_knowledge


class RagSearchInput(BaseModel):
    question: str = Field(description="要检索的问题")


@tool(args_schema=RagSearchInput)
async def rag_search(question: str) -> str:
    """知识库检索。"""
    return await retrieve_knowledge(question)
