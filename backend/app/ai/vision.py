"""
多模态视觉分析模块
使用 DashScope MultiModalConversation 分析菜品图片
"""
import base64
import asyncio
import os
from typing import Optional

from dashscope import MultiModalConversation

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

        messages = [
            {
                "role": "user",
                "content": [
                    {"image": data_uri},
                    {"text": "请简要描述这张图片里的菜品。只需说明：主要食材、颜色、外观特征、可能的烹饪方式。控制在50字以内，不要多余解释。"}
                ]
            }
        ]

        model = settings.vision_model
        logger.info(f"[Vision] 调用多模态模型: {model}")

        # MultiModalConversation.call 是同步阻塞的，用线程池包装
        api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: MultiModalConversation.call(
                model=model,
                messages=messages,
                api_key=api_key or None
            )
        )

        if response.status_code == 200:
            content = response.output.choices[0].message.content
            # content 可能是字符串或 list[dict]
            if isinstance(content, list):
                text_parts = [
                    c.get("text", "") for c in content
                    if isinstance(c, dict) and "text" in c
                ]
                description = " ".join(text_parts).strip()
            else:
                description = str(content).strip()

            logger.info(f"[Vision] 图片分析结果: {description}")
            return description
        else:
            logger.warning(
                f"[Vision] 模型调用失败: status={response.status_code}, "
                f"message={getattr(response, 'message', 'unknown')}"
            )
            return ""

    except Exception as e:
        logger.error(f"[Vision] 图片分析异常: {e}")
        return ""
