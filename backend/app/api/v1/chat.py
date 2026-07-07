"""
聊天路由
核心AI交互入口 - 支持同步JSON和SSE流式输出
"""
import json
import asyncio
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis, is_redis_available
from app.core.logging_config import get_logger
from app.api.deps import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import process_chat

logger = get_logger(__name__)

router = APIRouter()

# 限流配置
_RATE_LIMIT_WINDOW = 60  # 秒
_RATE_LIMIT_MAX = 20  # 每窗口最大请求数

# 聊天处理超时（秒），避免 LLM/RAG 不稳定时长时间挂起
_CHAT_TIMEOUT = 60


async def _check_rate_limit(user_id: int):
    """基于 Redis 的滑动窗口限流"""
    if not is_redis_available():
        return

    redis_client = get_redis()
    key = f"rate_limit:chat:{user_id}"
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, _RATE_LIMIT_WINDOW)
        if current > _RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，请稍后再试（每 {_RATE_LIMIT_WINDOW} 秒最多 {_RATE_LIMIT_MAX} 次）",
            )
    except HTTPException:
        raise
    except Exception as e:
        # Redis 异常时不阻塞业务，仅记录
        print(f"[RateLimit] 限流检查异常: {e}")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """聊天接口（同步JSON返回，向后兼容）"""
    # 优先从 JWT 获取用户身份，防止前端伪造 user_id
    user_id = current_user.get("id", data.user_id)
    try:
        await _check_rate_limit(user_id)
        # 图片搜菜涉及视觉模型 + LLM 匹配，耗时较长，单独放宽超时
        timeout = _CHAT_TIMEOUT if not data.image_base64 else 100
        result = await asyncio.wait_for(
            process_chat(
                db=db,
                user_id=user_id,
                message=data.message,
                cart=data.cart or [],
                image_base64=data.image_base64,
            ),
            timeout=timeout,
        )
        return ChatResponse(
            response=result["response"],
            cart=result["cart"],
            intent=result.get("intent"),
            agent=result.get("agent"),
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="AI 处理超时，请稍后重试或简化您的问题",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[Chat] 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"服务异常: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """聊天接口（SSE流式输出）"""
    user_id = current_user.get("id", data.user_id)
    await _check_rate_limit(user_id)

    async def event_generator():
        try:
            # 1. 先完整执行多智能体流程（Tool Calling 不适合流式）
            # 图片搜菜耗时较长，放宽超时
            timeout = _CHAT_TIMEOUT if not data.image_base64 else 100
            result = await asyncio.wait_for(
                process_chat(
                    db=db,
                    user_id=user_id,
                    message=data.message,
                    cart=data.cart or [],
                    image_base64=data.image_base64,
                ),
                timeout=timeout,
            )
            response_text = result.get("response", "")
            new_cart = result.get("cart", data.cart or [])

            # 2. 将 response 文本逐字符 SSE 发送（打字机效果）
            for char in response_text:
                payload = json.dumps({"type": "text", "content": char}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.015)  # 15ms/字，约67字/秒

            # 3. 发送结束事件，附带 cart 数据
            done_payload = json.dumps({"type": "done", "cart": new_cart}, ensure_ascii=False)
            yield f"data: {done_payload}\n\n"

        except Exception as e:
            logger.exception(f"[ChatStream] 处理失败: {e}")
            err_payload = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
