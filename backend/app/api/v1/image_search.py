"""
图片搜索路由（拍照搜菜）
流程：多模态模型分析图片 → LLM 匹配菜单 → 返回推荐
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.services.image_search_service import (
    _ALLOWED_IMAGE_TYPES,
    _IMAGE_MAGIC,
    search_dishes_by_image,
)

logger = get_logger(__name__)

router = APIRouter()


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

        mime_type = file.content_type or ""
        if mime_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="仅支持 jpeg/png/webp/gif 格式的图片")

        # 文件头校验
        valid_magic = any(contents.startswith(magic) for magic in _IMAGE_MAGIC)
        if not valid_magic:
            raise HTTPException(status_code=400, detail="上传文件不是有效的图片")

        # 复用共享服务完成"多模态分析 + LLM 匹配"
        result = await search_dishes_by_image(contents, mime_type, db)

        if not result["description"]:
            return {"response": "图片识别失败，请尝试上传更清晰的菜品照片。"}

        if not result["found"]:
            return {"response": "没有搜到符合图片描述的菜品。"}

        # 格式化返回（补充真实价格和描述）
        menu_items = result["menu_items"]
        matches = result["matches"]
        lines = ["图片已接收，根据图片特征为您推荐以下菜品："]
        for m in matches[:3]:
            name = m.get("name", "")
            reason = m.get("reason", "")
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
