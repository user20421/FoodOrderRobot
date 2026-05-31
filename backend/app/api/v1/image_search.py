"""
图片搜索路由（拍照搜菜）
流程：多模态模型分析图片 → LLM 匹配菜单 → 返回推荐
"""
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage

from app.core.database import get_db
from app.core.config import settings
from app.core.logging_config import get_logger
from app.ai.vision import analyze_dish_image
from app.ai.llm import get_llm
from app.repositories.menu_repo import menu_item_repo

logger = get_logger(__name__)

router = APIRouter()

# 图片搜索 LLM 匹配 Prompt
_IMAGE_MATCH_PROMPT = """你是一位菜品识别专家。用户上传了一张菜品图片，多模态模型已分析出以下描述：

【图片描述】
{description}

【餐厅菜单】
{menu_text}

请根据图片描述，从菜单中找出最可能匹配的 **最多3道** 菜品。
匹配规则：
1. 必须根据图片实际内容判断，不要凭空猜测
2. 如果图片明显不是菜品（如风景、人物、文字截图等），直接返回空列表
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


async def _match_dishes_with_llm(description: str, menu_items: list) -> list:
    """用LLM根据图片描述匹配菜单菜品"""
    if not menu_items:
        return []

    # 构建菜单文本
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

        result = json.loads(text)
        if result.get("found") and result.get("matches"):
            return result["matches"]
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"[ImageSearch] LLM 返回非JSON: {raw[:200]} | error: {e}")
        return []
    except Exception as e:
        logger.error(f"[ImageSearch] LLM 匹配失败: {e}")
        return []


@router.post("/image/search")
async def image_search(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传图片搜索菜品"""
    try:
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片大小不能超过5MB")

        mime_type = file.content_type or "image/jpeg"

        # 1. 多模态模型分析图片 → 短摘要
        description = await analyze_dish_image(contents, mime_type)
        if not description:
            return {"response": "图片识别失败，请尝试上传更清晰的菜品照片。"}

        # 2. 获取全部菜单
        menu_items = await menu_item_repo.get_all(db)
        if not menu_items:
            return {"response": "菜单数据为空，无法匹配菜品。"}

        # 3. LLM 根据摘要匹配最可能的菜品
        matches = await _match_dishes_with_llm(description, menu_items)

        if not matches:
            return {"response": "没有搜到符合图片描述的菜品。"}

        # 4. 格式化返回（补充真实价格和描述）
        lines = ["图片已接收，根据图片特征为您推荐以下菜品："]
        for m in matches[:3]:
            name = m.get("name", "")
            reason = m.get("reason", "")
            # 从菜单数据中查找真实信息
            item = next((i for i in menu_items if i.name == name), None)
            if item:
                lines.append(f"• {item.name}（{item.price:.0f}元）- {reason}")
            else:
                lines.append(f"• {name} - {reason}")

        response_text = "\n".join(lines)
        logger.info(f"[ImageSearch] 匹配结果: {response_text[:100]}...")
        return {"response": response_text}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ImageSearch] 图片搜索失败: {e}")
        raise HTTPException(status_code=500, detail="图片识别失败，请稍后重试")
