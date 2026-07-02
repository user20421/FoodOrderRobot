# -*- coding: utf-8 -*-
"""
Fast Router 单元测试
验证规则快速通道命中与未命中行为。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.ai.routing.fast_router import try_fast_path


class MockDB:
    pass


def _mock_item(name: str, price: float, item_id: int = 1):
    item = MagicMock()
    item.name = name
    item.price = price
    item.id = item_id
    return item


def _async_value(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner


class TestFastRouter:
    def run_async(self, coro):
        return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)

    def test_confirm_order_empty_cart(self):
        result = self.run_async(try_fast_path("确认下单", [], MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_order"
        assert "购物车为空" in result["response"]

    def test_view_cart(self):
        cart = [{"name": "麻婆豆腐", "quantity": 1, "unit_price": 28.0}]
        result = self.run_async(try_fast_path("看看购物车", cart, MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_order"
        assert "麻婆豆腐" in result["response"]

    def test_clear_cart(self):
        cart = [{"name": "麻婆豆腐", "quantity": 1, "unit_price": 28.0}]
        result = self.run_async(try_fast_path("清空购物车", cart, MockDB(), 1))
        assert result is not None
        assert result["cart"] == []

    def test_faq_business_hours(self):
        result = self.run_async(try_fast_path("你们几点开门", [], MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_service"
        assert "11:00" in result["response"]

    @patch("app.ai.routing.fast_router._get_menu_item_names")
    @patch("app.ai.routing.fast_router.menu_service.get_item_by_name")
    def test_add_to_cart(self, mock_get_item, mock_names):
        mock_names.return_value = ["麻婆豆腐"]
        mock_get_item.return_value = _mock_item("麻婆豆腐", 28.0, 4)
        result = self.run_async(try_fast_path("来一份麻婆豆腐", [], MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_order"
        assert any(c["name"] == "麻婆豆腐" for c in result["cart"])

    @patch("app.ai.routing.fast_router._get_menu_item_names")
    @patch("app.ai.routing.fast_router.menu_service.get_item_by_name")
    def test_add_multiple_dishes(self, mock_get_item, mock_names):
        mock_names.return_value = ["麻婆豆腐", "毛血旺", "白米饭"]
        items = {
            "麻婆豆腐": _mock_item("麻婆豆腐", 28.0, 4),
            "毛血旺": _mock_item("毛血旺", 68.0, 2),
        }
        mock_get_item.side_effect = lambda db, name: items.get(name)
        result = self.run_async(try_fast_path("来一份麻婆豆腐，再来两份毛血旺", [], MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_order"
        names = {c["name"] for c in result["cart"]}
        assert names == {"麻婆豆腐", "毛血旺"}
        mao = next(c for c in result["cart"] if c["name"] == "毛血旺")
        assert mao["quantity"] == 2

    @patch("app.ai.routing.fast_router._get_menu_item_names")
    @patch("app.ai.routing.fast_router.menu_service.get_item_by_name")
    def test_mixed_intent_goes_to_agent(self, mock_get_item, mock_names):
        mock_names.return_value = ["麻婆豆腐", "毛血旺"]
        result = self.run_async(
            try_fast_path("来一份麻婆豆腐，再来两份毛血旺。然后告诉我你们的营业时间", [], MockDB(), 1)
        )
        # 混合意图应返回 None，由上层 Agent 处理
        assert result is None

    @patch("app.ai.routing.fast_router._get_menu_item_names")
    @patch("app.ai.routing.fast_router.menu_service.get_item_by_name")
    def test_polite_order_not_mixed(self, mock_get_item, mock_names):
        """带语气词的纯点餐请求（如"可以给我来一杯可乐吗"）应被快速通道处理，不被误判为混合意图。"""
        mock_names.return_value = ["可乐"]
        mock_get_item.return_value = _mock_item("可乐", 12.0, 5)
        result = self.run_async(try_fast_path("可以给我来一杯可乐吗？", [], MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_order"
        assert any(c["name"] == "可乐" for c in result["cart"])

    @patch("app.ai.routing.fast_router._get_menu_item_names")
    @patch("app.ai.routing.fast_router.menu_service.get_item_by_name")
    def test_order_with_invoice_is_mixed(self, mock_get_item, mock_names):
        """点餐 + 开发票属于混合意图，应交 Agent 统一处理。"""
        mock_names.return_value = ["麻婆豆腐"]
        result = self.run_async(try_fast_path("来一份麻婆豆腐，再给我开张发票", [], MockDB(), 1))
        assert result is None

    @patch("app.ai.routing.fast_router._get_menu_item_names")
    @patch("app.ai.routing.fast_router.menu_service.get_item_by_name")
    def test_omitted_quantity_with_unit(self, mock_get_item, mock_names):
        """省略数量仅用单位，如"来碗白米饭"，应正确识别为 1 份。"""
        mock_names.return_value = ["白米饭"]
        mock_get_item.return_value = _mock_item("白米饭", 3.0, 6)
        result = self.run_async(try_fast_path("来碗白米饭", [], MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_order"
        rice = next(c for c in result["cart"] if c["name"] == "白米饭")
        assert rice["quantity"] == 1

    @patch("app.ai.routing.fast_router._get_menu_item_names")
    @patch("app.ai.routing.fast_router.menu_service.get_item_by_name")
    def test_bare_verb_dish_name(self, mock_get_item, mock_names):
        """"点 + 菜名"这种省略数量的说法应被识别，但"几点"类时间询问不应误判为点餐。"""
        mock_names.return_value = ["宫保鸡丁"]
        mock_get_item.return_value = _mock_item("宫保鸡丁", 32.0, 7)
        result = self.run_async(try_fast_path("点宫保鸡丁", [], MockDB(), 1))
        assert result is not None
        assert result["agent"] == "fast_order"
        assert any(c["name"] == "宫保鸡丁" for c in result["cart"])

    def test_no_match(self):
        result = self.run_async(try_fast_path("这个菜怎么做", [], MockDB(), 1))
        assert result is None
