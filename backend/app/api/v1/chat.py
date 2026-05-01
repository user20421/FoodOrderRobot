"""
聊天 API
POST /api/v1/chat
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.ai.supervisor import run_chat
from app.repositories.chat import save_chat_message

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    智能点餐对话接口
    输入: user_id, message, [cart]
    输出: response, cart
    """
    # 将 CartItem 模型转换为 dict，保持与下层代码兼容
    cart_data = [item.model_dump() for item in req.cart] if req.cart else []

    result = await run_chat(
        user_id=req.user_id,
        message=req.message,
        cart=cart_data,
    )

    # 保存聊天历史（降级处理：不阻塞主流程）
    try:
        await save_chat_message(db, req.user_id, "user", req.message)
        await save_chat_message(db, req.user_id, "assistant", result["response"])
    except Exception as e:
        print(f"[Chat] 保存聊天记录失败: {e}")

    return ChatResponse(response=result["response"], cart=result.get("cart", []))
