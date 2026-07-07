"""
LLM Classifier 单元测试
使用 Mock LLM 验证分类器行为。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from app.ai.routing.llm_classifier import classify_message, generate_direct_reply


def _async_result(value):
    """创建一个返回 value 的异步函数"""
    async def _inner(*args, **kwargs):
        return value
    return _inner


class TestLLMClassifier:
    def run_async(self, coro):
        return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)

    def test_greeting_pattern_short_circuits(self):
        result = self.run_async(classify_message("你好"))
        assert result is not None
        assert result["route"] == "greeting"
        assert result["answer"]  # 直接返回模板回复

    def test_greeting_who_are_you(self):
        """'你是谁'应被识别为问候并直接返回模板。"""
        result = self.run_async(classify_message("你好，你是谁"))
        assert result is not None
        assert result["route"] == "greeting"
        assert "小餐" in result["answer"]

    @patch("app.ai.routing.llm_classifier.get_llm")
    def test_classify_agent(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"route": "agent", "reason": "需要查订单"}'
        mock_llm.ainvoke = _async_result(mock_response)
        mock_get_llm.return_value = mock_llm

        result = self.run_async(classify_message("我的订单在哪里"))
        assert result is None  # agent 返回 None，让 chat_service 继续走 Agent 图

    @patch("app.ai.routing.llm_classifier.get_llm")
    def test_classify_faq_direct(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"route": "faq_direct", "reason": "常见问题"}'
        mock_llm.ainvoke = _async_result(mock_response)
        mock_get_llm.return_value = mock_llm

        result = self.run_async(classify_message("你们有什么特色菜"))
        assert result is not None
        assert result["route"] == "faq_direct"

    @patch("app.ai.routing.llm_classifier.get_llm")
    def test_generate_direct_reply(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "您好，欢迎光临！"
        mock_llm.ainvoke = _async_result(mock_response)
        mock_get_llm.return_value = mock_llm

        reply = self.run_async(generate_direct_reply("你好"))
        assert "欢迎" in reply
