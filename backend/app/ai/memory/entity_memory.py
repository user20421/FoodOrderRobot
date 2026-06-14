"""
实体记忆 / 用户画像
提取并存储用户偏好、忌口、常点菜品等实体信息
存储在 MongoDB user_profiles 集合中（使用 Beanie ODM）
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage

from app.ai.llm import get_llm
from app.core.mongodb import is_mongodb_available, is_beanie_initialized
from app.core.logging_config import get_logger
from app.documents.profile import UserProfileDocument

logger = get_logger(__name__)


class EntityMemory:
    """
    用户实体记忆
    结构化的用户画像，包括：
    - 口味偏好（辣度、酸甜等）
    - 常点菜品
    - 用餐习惯
    注意：不提取忌口、过敏、饮食限制等可能干扰正常下单的信息。
    """

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0.1)
        return self._llm

    async def extract_entities(self, dialogue: str, existing_profile: dict = None) -> dict:
        """从对话中提取用户实体信息"""
        try:
            llm = self._get_llm()
            existing = ""
            if existing_profile:
                existing = f"\n现有用户画像：{existing_profile}\n请在此基础上补充或更新。\n"

            prompt = (
                f"请从以下客服对话中提取用户的偏好信息，以JSON格式输出。{existing}\n"
                f"需要提取的字段（没有则留空或不包含）：\n"
                f"- preferred_spicy_level: 偏好的辣度（不辣/微辣/中辣/重辣）\n"
                f"- favorite_dishes: 喜欢的菜品列表\n"
                f"- dining_style: 用餐习惯（如聚餐、快餐、健康等）\n\n"
                f"注意：不要提取忌口、过敏、饮食限制（如素食、清真）等信息，这些信息不得影响用户正常点餐。\n\n"
                f"对话内容：\n{dialogue}\n\n"
                f"只输出JSON，不要解释："
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            text = response.content.strip()

            import json
            text = text.replace("```json", "").replace("```", "").strip()
            entities = json.loads(text)
            return entities
        except Exception as e:
            logger.warning(f"[EntityMemory] 提取实体失败: {e}")
            return {}

    async def update_profile(self, user_id: int, new_entities: dict):
        """更新用户画像"""
        if not is_mongodb_available() or not is_beanie_initialized():
            return
        try:
            doc = await UserProfileDocument.find_one(UserProfileDocument.user_id == user_id)
            if doc:
                profile = doc.profile or {}
                for key, value in new_entities.items():
                    if isinstance(value, list) and key in profile:
                        old_list = profile.get(key, [])
                        if isinstance(old_list, list):
                            merged = list(set(old_list + value))
                            profile[key] = merged
                        else:
                            profile[key] = value
                    else:
                        if value:
                            profile[key] = value
                # 清理已废弃的忌口/饮食限制字段，避免历史数据影响正常点餐
                for deprecated_key in ("dislikes", "allergies", "dietary_restrictions"):
                    profile.pop(deprecated_key, None)
                doc.profile = profile
                doc.updated_at = datetime.now(timezone.utc)
                await doc.save()
            else:
                profile = {k: v for k, v in new_entities.items() if v}
                # 清理已废弃的忌口/饮食限制字段
                for deprecated_key in ("dislikes", "allergies", "dietary_restrictions"):
                    profile.pop(deprecated_key, None)
                await UserProfileDocument(
                    user_id=user_id,
                    profile=profile,
                ).insert()
        except Exception as e:
            logger.warning(f"[EntityMemory] 更新画像失败: {e}")

    async def get_profile(self, user_id: int) -> dict:
        """获取用户画像"""
        if not is_mongodb_available() or not is_beanie_initialized():
            return {}
        try:
            doc = await UserProfileDocument.find_one(UserProfileDocument.user_id == user_id)
            return doc.profile if doc else {}
        except Exception as e:
            logger.warning(f"[EntityMemory] 读取画像失败: {e}")
            return {}

    def format_profile_for_prompt(self, profile: dict) -> str:
        """将画像格式化为提示词文本"""
        if not profile:
            return ""
        lines = ["## 用户偏好画像"]
        mapping = {
            "preferred_spicy_level": "偏好辣度",
            "favorite_dishes": "喜欢菜品",
            "dining_style": "用餐习惯",
        }
        for key, label in mapping.items():
            value = profile.get(key)
            if value:
                if isinstance(value, list):
                    value = "、".join(value)
                lines.append(f"- {label}：{value}")
        return "\n".join(lines) if len(lines) > 1 else ""
