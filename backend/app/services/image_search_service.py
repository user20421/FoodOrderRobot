"""
图片搜菜共享服务
封装"多模态分析 + LLM 菜单匹配"流程，供独立 /image/search 接口和聊天流程复用。
"""
import base64
import json
import re
from typing import List, Dict, Tuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.ai.vision import analyze_dish_image
from app.ai.llm import get_llm
from app.ai.agents.prompts import PromptBuilder
from app.services import menu_service
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# 允许的图片 MIME 类型
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# 文件头 magic number（用于二次校验）
# 注意：RIFF 文件头也用于 WAV/AVI 等，因此 WebP 需要额外检查 bytes[8:12] == b"WEBP"
IMAGE_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


class DishMatch(BaseModel):
    name: str = Field(..., description="菜品名称")
    reason: str = Field(default="", description="匹配理由")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")


class ImageSearchResult(BaseModel):
    found: bool = Field(default=False)
    matches: List[DishMatch] = Field(default_factory=list)


# 图片匹配提示词已从 prompts/services/image_search.md 迁移，由 PromptBuilder 加载。


def _detect_mime_type(image_bytes: bytes, declared_mime: str) -> str:
    """根据文件头检测 MIME 类型，并对 WebP 做额外校验。"""
    detected = None
    for magic, mt in IMAGE_MAGIC.items():
        if image_bytes.startswith(magic):
            detected = mt
            break

    if detected == "image/webp":
        # RIFF 容器需要确认是 WebP 而不是 WAV/AVI
        if len(image_bytes) < 12 or image_bytes[8:12] != b"WEBP":
            detected = None

    # 文件头可信时优先使用文件头结果
    if detected:
        return detected

    # 文件头无法识别时，回退到声明的 MIME（仍需在白名单内）
    if declared_mime in ALLOWED_IMAGE_TYPES:
        return declared_mime

    raise ValueError("仅支持 jpeg/png/webp/gif 格式的图片")


async def decode_image_base64(image_base64: str) -> Tuple[bytes, str]:
    """
    解码前端上传的 base64 图片。
    支持 data:image/xxx;base64,xxx 格式或纯 base64 字符串。
    返回 (image_bytes, mime_type)。
    """
    if not image_base64:
        raise ValueError("图片内容为空")

    # 处理 data URI 前缀
    if "," in image_base64:
        header, data = image_base64.split(",", 1)
        mime_type = header.split(";")[0].replace("data:", "").strip().lower()
        if not mime_type:
            mime_type = "image/jpeg"
    else:
        data = image_base64
        mime_type = "image/jpeg"

    try:
        image_bytes = base64.b64decode(data)
    except Exception as e:
        raise ValueError(f"图片 Base64 解码失败: {e}")

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ValueError("图片大小不能超过5MB")

    mime_type = _detect_mime_type(image_bytes, mime_type)
    return image_bytes, mime_type


def _build_menu_text(menu_items: List[Dict]) -> str:
    """把菜单列表格式化为给 LLM 的文本。"""
    lines = []
    for idx, item in enumerate(menu_items, 1):
        line = f"{idx}. {item['name']}（¥{item['price']:.0f}）"
        if item.get("description"):
            line += f" - {item['description']}"
        if item.get("tags"):
            line += f" - 标签:{item['tags']}"
        lines.append(line)
    return "\n".join(lines)


def _extract_json(text: str) -> Optional[str]:
    """从 LLM 输出中提取 JSON 块。"""
    # 优先 markdown 代码块
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    # 尝试从文本中找第一个 { 开头、最后一个 } 结尾的 JSON 对象
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


async def match_dishes_with_llm(description: str, menu_items: List[Dict]) -> List[Dict]:
    """用 LLM 根据图片描述匹配菜单菜品，返回匹配列表。"""
    if not menu_items:
        return []

    menu_text = _build_menu_text(menu_items)
    prompt = PromptBuilder.build_image_search_prompt(description=description, menu_text=menu_text)

    try:
        llm = get_llm(temperature=0.1)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = str(response.content).strip()

        if not raw:
            logger.warning("[ImageSearchService] LLM 返回空内容")
            return []

        text = _extract_json(raw)
        if text is None:
            logger.warning(f"[ImageSearchService] 无法从 LLM 输出中提取 JSON: {raw[:200]}")
            return []

        result = ImageSearchResult.model_validate_json(text)
        if not result.found or not result.matches:
            return []

        # 校验匹配结果是否真实存在于菜单中
        valid_names = {item["name"] for item in menu_items}
        valid_matches = []
        for m in result.matches:
            if m.name in valid_names:
                valid_matches.append(m.model_dump())
            else:
                logger.warning(f"[ImageSearchService] LLM 返回的菜品不在菜单中: {m.name}")
        return valid_matches

    except Exception as e:
        logger.error(f"[ImageSearchService] LLM 匹配失败: {e}", exc_info=True)
        return []


def _looks_like_food(description: str) -> bool:
    """简单判断图片描述是否像食物，避免非食物图片被 fallback 误匹配。"""
    food_keywords = [
        "肉", "鱼", "鸡", "鸭", "牛", "羊", "猪", "虾", "蟹", "蛋", "豆腐",
        "菜", "蔬", "饭", "面", "汤", "炒", "烧", "煮", "炖", "烤", "蒸",
        "红烧", "麻辣", "清蒸", "油炸", "煲", "锅", "盘", "食材"
    ]
    desc = description.lower()
    return any(k in desc for k in food_keywords)


def _keyword_fallback(description: str, menu_items: List[Dict]) -> List[Dict]:
    """LLM 失败或结果为空时的简单关键词 fallback。"""
    if not description or not menu_items:
        return []

    # 从描述中提取可能的食材/做法关键词（简单按字符/词匹配）
    desc = description.lower()
    matches = []
    for item in menu_items:
        score = 0
        name = item.get("name", "")
        tags = item.get("tags") or ""
        item_desc = item.get("description") or ""
        text = f"{name} {tags} {item_desc}"

        # 菜名命中权重高
        if name and len(name) >= 2 and name in desc:
            score += 3
        # 标签/描述中的词命中
        for token in re.split(r"[,，、\s]+", text):
            token = token.strip()
            if len(token) >= 2 and token in desc:
                score += 1

        if score > 0:
            matches.append({
                "name": name,
                "reason": "根据图片描述关键词匹配",
                "confidence": min(0.6 + score * 0.1, 0.9),
            })

    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches[:3]


async def _load_menu_dicts(db: AsyncSession) -> List[Dict]:
    """加载菜单并序列化为字典；优先使用 menu_service 的 Redis 缓存。"""
    try:
        items = await menu_service.get_menu_items(db)
        return [
            {
                "id": item.id,
                "name": item.name,
                "price": float(item.price),
                "description": item.description or "",
                "tags": item.tags or "",
            }
            for item in items
        ]
    except Exception as e:
        logger.error(f"[ImageSearchService] 加载菜单失败: {e}", exc_info=True)
        return []


def format_image_search_response(result: Dict) -> str:
    """把图片搜菜结果格式化为最终回复文本（供聊天流与独立 API 共用）。"""
    description = result.get("description", "")
    if not description:
        return "图片识别失败，请尝试上传更清晰的菜品照片。"

    if not result.get("found"):
        return (
            f"图片看起来是：{description}\n"
            f"抱歉，本店菜单中没有找到与这道菜相同或非常相似的菜品。"
        )

    menu_items = result.get("menu_items", [])
    matches = result.get("matches", [])
    lines = [f"图片看起来是：{description}", "根据图片特征，本店有以下相似菜品："]
    for m in matches[:3]:
        name = m.get("name", "")
        reason = m.get("reason", "")
        item = next((i for i in menu_items if i.get("name") == name), None)
        if item:
            lines.append(f"• {item['name']}（¥{item['price']:.0f}）- {reason}")
        else:
            lines.append(f"• {name} - {reason}")
    return "\n".join(lines)


async def search_dishes_by_image(
    image_bytes: bytes,
    mime_type: str,
    db: AsyncSession,
) -> Dict:
    """
    图片搜菜主流程：多模态分析 → 菜单匹配。
    返回字段：
        found: bool         是否匹配到菜品
        description: str    多模态模型生成的图片描述
        matches: List[Dict] 匹配结果列表
        menu_items: List[Dict] 原始菜单数据（字典形式，避免 ORM 过期问题）
    """
    # 1. 先加载菜单并立即序列化为字典，避免后续 LLM 异步调用导致 ORM 对象过期
    menu_items = await _load_menu_dicts(db)

    # 2. 视觉模型分析图片
    description = await analyze_dish_image(image_bytes, mime_type)
    if not description:
        return {
            "found": False,
            "description": "",
            "matches": [],
            "menu_items": menu_items,
        }

    if not menu_items:
        return {
            "found": False,
            "description": description,
            "matches": [],
            "menu_items": [],
        }

    # 3. LLM 匹配
    matches = await match_dishes_with_llm(description, menu_items)

    # 4. 如果 LLM 没结果，尝试关键词 fallback（仅在描述看起来像食物时）
    if not matches and _looks_like_food(description):
        matches = _keyword_fallback(description, menu_items)

    return {
        "found": bool(matches),
        "description": description,
        "matches": matches,
        "menu_items": menu_items,
    }
