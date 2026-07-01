"""
LLM 工厂
统一管理大模型实例，避免重复初始化
"""
import os
from typing import Optional, Dict

from langchain_community.chat_models import ChatZhipuAI
from langchain_community.embeddings import ZhipuAIEmbeddings

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_llm_instances: Dict[tuple, ChatZhipuAI] = {}
_embedding_instance: Optional[ZhipuAIEmbeddings] = None


class _MockLLM:
    """Mock LLM，用于 API Key 未设置时的优雅降级"""
    async def ainvoke(self, messages, **kwargs):
        raise ValueError("ZHIPU_API_KEY 未设置，AI 服务不可用")
    def bind_tools(self, tools, **kwargs):
        return self


def get_llm(temperature: float = 0.1):
    """
    获取 LLM 实例。
    按 (model, temperature) 组合缓存，避免不同温度需求复用同一实例。
    """
    global _llm_instances

    api_key = settings.zhipu_api_key or os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        logger.warning("ZHIPU_API_KEY 未设置，AI 服务将不可用")
        return _MockLLM()

    cache_key = (settings.chat_model, temperature)
    if cache_key not in _llm_instances:
        _llm_instances[cache_key] = ChatZhipuAI(
            model=settings.chat_model,
            api_key=api_key,
            temperature=temperature,
        )
        logger.info(f"LLM 初始化完成: {settings.chat_model}, temperature={temperature}")

    return _llm_instances[cache_key]


def get_embedding() -> ZhipuAIEmbeddings:
    """获取 Embedding 实例"""
    global _embedding_instance
    if _embedding_instance is not None:
        return _embedding_instance

    api_key = settings.zhipu_api_key or os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        raise ValueError("ZHIPU_API_KEY 未设置")

    _embedding_instance = ZhipuAIEmbeddings(
        model=settings.embedding_model,
        api_key=api_key,
        dimensions=settings.embedding_dimensions,
    )
    logger.info(f"Embedding 初始化完成: {settings.embedding_model} ({settings.embedding_dimensions}D)")
    return _embedding_instance


async def check_llm_health() -> dict:
    """启动时检查 LLM 可用性，返回详细状态"""
    api_key = settings.zhipu_api_key or os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        return {"ok": False, "reason": "ZHIPU_API_KEY 未设置"}

    # 直接调用智谱 AI 测试当前模型
    try:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=api_key)

        resp = client.chat.completions.create(
            model=settings.chat_model,
            messages=[{"role": "user", "content": "hi"}],
        )
        if getattr(resp, "choices", None):
            return {"ok": True, "model": settings.chat_model}
        else:
            return {"ok": False, "reason": f"模型 '{settings.chat_model}' 返回异常: {resp}"}
    except Exception as e:
        return {"ok": False, "reason": f"智谱 AI 连接测试失败: {e}"}


def reset_llm():
    """重置 LLM 实例（用于切换模型等场景）"""
    global _llm_instances, _embedding_instance
    _llm_instances = {}
    _embedding_instance = None
