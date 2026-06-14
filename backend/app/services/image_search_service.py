"""
图片搜菜共享服务
封装"多模态分析 + LLM 菜单匹配"流程，供独立 /image/search 接口和聊天流程复用。
"""
import base64
import json
from typing import List, Dict, Tuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.ai.vision import analyze_dish_image
from app.ai.llm import get_llm
from app.repositories.menu_repo import menu_item_repo
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# 允许的图片 MIME 类型
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# 文件头 magic number（用于二次校验）
_IMAGE_MAGIC = {
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


_IMAGE_MATCH_PROMPT = """你是一位菜品识别专家。用户上传了一张菜品图片，多模态模型已分析出以下描述：

【图片描述】
{description}

【餐厅菜单】
{menu_text}

请根据图片描述，从菜单中找出最可能匹配的 **最多3道** 菜品。
匹配规则：
1. 必须根据图片实际内容判断，不要凭空猜测
2. 如果图片明显不是菜品（如风景、人物、文字截图、动物、物品等），直接返回空列表
3. 如果图片是菜品但菜单中没有相似的，也返回空列表
4. 只输出确定有较高匹配度的菜品，宁可少不要错

请严格按以下JSON格式输出，不要有任何其他文字：
{{
  "found": true/false,
  "matches": [
    {{"name": "菜品名称", "reason": "简短匹配理由（15字内）", "confidence": 0.95}}
  ]
}}
"""


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

    # 文件头校验优先
    detected_mime = None
    for magic, mt in _IMAGE_MAGIC.items():
        if image_bytes.startswith(magic):
            detected_mime = mt
            break

    if detected_mime:
        mime_type = detected_mime
    elif mime_type not in _ALLOWED_IMAGE_TYPES:
        raise ValueError("仅支持 jpeg/png/webp/gif 格式的图片")

    if mime_type not in _ALLOWED_IMAGE_TYPES:
        raise ValueError(f"不支持的图片格式: {mime_type}")

    return image_bytes, mime_type


async def match_dishes_with_llm(description: str, menu_items: list) -> List[Dict]:
    """用 LLM 根据图片描述匹配菜单菜品，返回匹配列表。"""
    if not menu_items:
        return []

    menu_lines = []
    for idx, item in enumerate(menu_items, 1):
        line = f"{idx}. {item.name}（{item.price:.0f}元）"
        if item.description:
            line += f" - {item.description}"
        if item.tags:
            line += f" - 标签:{item.tags}"
        menu_lines.append(line)
    menu_text = "\n".join(menu_lines)

    prompt = _IMAGE_MATCH_PROMPT.format(description=description, menu_text=menu_text)

    try:
        llm = get_llm(temperature=0.1)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # 尝试提取 JSON（处理 markdown 代码块包裹的情况）
        text = raw
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = ImageSearchResult.model_validate_json(text)
        if result.found and result.matches:
            return [m.model_dump() for m in result.matches]
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"[ImageSearchService] LLM 返回非JSON: {raw[:200]} | error: {e}")
        return []
    except Exception as e:
        logger.error(f"[ImageSearchService] LLM 匹配失败: {e}")
        return []


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
        menu_items: List    原始菜单对象列表
    """
    description = await analyze_dish_image(image_bytes, mime_type)
    if not description:
        return {
            "found": False,
            "description": "",
            "matches": [],
            "menu_items": [],
        }

    menu_items = await menu_item_repo.get_all(db)
    if not menu_items:
        return {
            "found": False,
            "description": description,
            "matches": [],
            "menu_items": [],
        }

    matches = await match_dishes_with_llm(description, menu_items)
    return {
        "found": bool(matches),
        "description": description,
        "matches": matches,
        "menu_items": menu_items,
    }
