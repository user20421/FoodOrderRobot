"""
ContentLoader 单元测试
验证 Markdown 加载、知识库解析、提示词渲染。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest

from app.core.content_loader import (
    load_markdown,
    render_template,
    get_menu_items,
    get_menu_categories,
    get_faq_data,
    get_store_docs,
    verify_knowledge_migration,
)
from app.ai.agents.prompts import PromptBuilder


class TestMarkdownLoading:
    def test_load_menu_markdown(self):
        content = load_markdown("knowledge/menu/menu.md")
        assert content.frontmatter.get("source") == "menu"
        assert "招牌水煮鱼" in content.body

    def test_load_prompt(self):
        prompt = PromptBuilder.load_prompt("supervisor")
        assert "Supervisor" in prompt or "调度员" in prompt
        assert "order|inquiry|recommend|service" in prompt

    def test_render_template(self):
        template = "你好，{{username}}！"
        assert render_template(template, {"username": "张三"}) == "你好，张三！"
        assert render_template(template, {}) == "你好，{{username}}！"


class TestKnowledgeParsing:
    def test_menu_items_count(self):
        items = get_menu_items()
        assert len(items) == 39

    def test_menu_items_structure(self):
        items = get_menu_items()
        item = items[0]
        assert "name" in item
        assert "price" in item
        assert "spicy_level" in item
        assert "category" in item
        assert item["category"] == "热菜"

    def test_menu_categories_count(self):
        cats = get_menu_categories()
        assert len(cats) == 7

    def test_faq_count(self):
        faqs = get_faq_data()
        assert len(faqs) == 20

    def test_store_docs_count(self):
        docs = get_store_docs()
        assert len(docs) == 6

    def test_verify_knowledge_migration(self):
        stats = verify_knowledge_migration()
        assert stats["menu_items"] == 39
        assert stats["categories"] == 7
        assert stats["faq"] == 20
        assert stats["store_docs"] == 6


class TestPromptBuilder:
    def test_build_supervisor_prompt(self):
        prompt = PromptBuilder.build_supervisor_prompt("你好")
        assert "调度员" in prompt

    def test_build_agent_prompt(self):
        prompt = PromptBuilder.build_agent_prompt(
            "order",
            cart=[{"name": "麻婆豆腐", "quantity": 1, "unit_price": 28.0}],
            user_id=1,
            user_identity="当前用户的名字是：张三",
        )
        assert "Order Agent" in prompt or "点餐助手" in prompt
        assert "麻婆豆腐" in prompt
        assert "张三" in prompt

    def test_build_greeting_prompt(self):
        prompt = PromptBuilder.build_greeting_prompt("你好", user_identity="张三")
        assert "友好" in prompt or "问候" in prompt
