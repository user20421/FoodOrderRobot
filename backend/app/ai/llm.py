"""
LLM 工厂
统一管理大模型实例，避免重复初始化
"""
import os
from typing import Optional, Dict

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings.dashscope import DashScopeEmbeddings

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_llm_instances: Dict[tuple, ChatTongyi] = {}
_embedding_instance: Optional[DashScopeEmbeddings] = None


class _MockLLM:
    """Mock LLM，用于 API Key 未设置时的优雅降级"""
    async def ainvoke(self, messages, **kwargs):
        raise ValueError("DASHSCOPE_API_KEY 未设置，AI 服务不可用")
    def bind_tools(self, tools, **kwargs):
        return self


def get_llm(temperature: float = 0.1):
    """
    获取 LLM 实例。
    按 (model, temperature) 组合缓存，避免不同温度需求复用同一实例。
    """
    global _llm_instances

    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        logger.warning("DASHSCOPE_API_KEY 未设置，AI 服务将不可用")
        return _MockLLM()

    cache_key = (settings.chat_model, temperature)
    if cache_key not in _llm_instances:
        _llm_instances[cache_key] = ChatTongyi(
            model=settings.chat_model,
            dashscope_api_key=api_key,
            temperature=temperature,
        )
        logger.info(f"LLM 初始化完成: {settings.chat_model}, temperature={temperature}")

    return _llm_instances[cache_key]


def get_embedding() -> DashScopeEmbeddings:
    """获取 Embedding 实例"""
    global _embedding_instance
    if _embedding_instance is not None:
        return _embedding_instance

    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未设置")

    _embedding_instance = DashScopeEmbeddings(
        model=settings.embedding_model,
        dashscope_api_key=api_key,
    )
    logger.info(f"Embedding 初始化完成: {settings.embedding_model}")
    return _embedding_instance


async def check_llm_health() -> dict:
    """启动时检查 LLM 可用性，返回详细状态"""
    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        return {"ok": False, "reason": "DASHSCOPE_API_KEY 未设置"}

    # 直接调用 DashScope 测试当前模型
    try:
        import dashscope
        from http import HTTPStatus
        from dashscope import Generation
        dashscope.api_key = api_key

        resp = Generation.call(
            model=settings.chat_model,
            messages=[{"role": "user", "content": "hi"}],
            result_format="message"
        )
        if resp.status_code == HTTPStatus.OK:
            return {"ok": True, "model": settings.chat_model}
        else:
            reason = getattr(resp, "message", str(resp.status_code))
            return {"ok": False, "reason": f"模型 '{settings.chat_model}' 不可用: {reason}"}
    except Exception as e:
        return {"ok": False, "reason": f"DashScope 连接测试失败: {e}"}


def reset_llm():
    """重置 LLM 实例（用于切换模型等场景）"""
    global _llm_instance, _embedding_instance, _last_model
    _llm_instance = None
    _embedding_instance = None
    _last_model = ""
