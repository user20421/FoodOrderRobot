"""
多模态视觉分析模块
使用智谱 AI 多模态模型分析菜品图片
"""
import base64
import asyncio
import os
from typing import Optional

from langchain_community.chat_models import ChatZhipuAI
from langchain_core.messages import HumanMessage

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def analyze_dish_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """
    用多模态模型分析菜品图片，返回短摘要描述。

    返回格式示例："红亮的麻辣豆腐，表面撒有绿色葱花和花椒粉"
    """
    try:
        base64_str = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{base64_str}"

        api_key = settings.zhipu_api_key or os.environ.get("ZHIPU_API_KEY", "")
        if not api_key:
            logger.warning("[Vision] ZHIPU_API_KEY 未设置，无法分析图片")
            return ""

        model = settings.vision_model
        logger.info(f"[Vision] 调用多模态模型: {model}")

        llm = ChatZhipuAI(
            model=model,
            api_key=api_key,
            temperature=0.1,
        )

        message = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": "请简要描述这张图片里的菜品。只需说明：主要食材、颜色、外观特征、可能的烹饪方式。控制在50字以内，不要多余解释。"}
        ])

        # ChatZhipuAI 的 ainvoke 是异步的
        response = await llm.ainvoke([message])
        description = str(response.content).strip()

        logger.info(f"[Vision] 图片分析结果: {description}")
        return description

    except Exception as e:
        logger.error(f"[Vision] 图片分析异常: {e}")
        return ""
