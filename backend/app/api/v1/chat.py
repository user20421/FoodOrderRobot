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
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import process_chat

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """聊天接口（同步JSON返回，向后兼容）"""
    try:
        result = await process_chat(
            db=db,
            user_id=data.user_id,
            message=data.message,
            cart=data.cart or [],
        )
        return ChatResponse(
            response=result["response"],
            cart=result["cart"],
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"服务异常: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """聊天接口（SSE流式输出）"""
    async def event_generator():
        try:
            # 1. 先完整执行多智能体流程（Tool Calling 不适合流式）
            result = await process_chat(
                db=db,
                user_id=data.user_id,
                message=data.message,
                cart=data.cart or [],
            )
            response_text = result.get("response", "")
            new_cart = result.get("cart", data.cart or [])

            # 2. 将 response 文本逐字符 SSE 发送（打字机效果）
            for char in response_text:
                payload = json.dumps({"type": "text", "content": char}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.025)  # 25ms/字，约40字/秒

            # 3. 发送结束事件，附带 cart 数据
            done_payload = json.dumps({"type": "done", "cart": new_cart}, ensure_ascii=False)
            yield f"data: {done_payload}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
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
