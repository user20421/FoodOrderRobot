"""
聊天服务
整合多智能体、记忆管理和RAG
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.ai.graph.builder import get_agent_graph
from app.ai.memory.manager import MemoryManager
from app.repositories.chat_repo import chat_repo
from app.repositories.user_repo import user_repo


_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取记忆管理器单例"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


async def _get_user_identity(db: AsyncSession, user_id: int) -> str:
    """获取用户身份信息，用于提示词注入"""
    try:
        user = await user_repo.get_by_id(db, user_id)
        if user:
            return (
                f"## 当前用户\n"
                f"当前用户的名字是：{user.username}\n"
                f"请在回复中自然地称呼他/她，让对话更亲切。"
                f"例如：'{user.username}，已为您...' 或 '欢迎，{user.username}！'"
            )
    except Exception:
        pass
    return ""


async def process_chat(
    db: AsyncSession,
    user_id: int,
    message: str,
    cart: list = None,
) -> dict:
    """
    处理聊天消息
    1. 加载记忆上下文
    2. 调用多智能体图
    3. 保存消息记录
    """
    cart = cart or []
    memory_manager = get_memory_manager()

    # 加载对话上下文
    history_messages, summary = await memory_manager.get_conversation_context(user_id)

    # 获取用户身份信息（用户名等）
    user_identity = await _get_user_identity(db, user_id)
    # 合并用户画像（MongoDB 中的偏好信息）
    user_profile = await memory_manager.get_user_profile_text(user_id)
    full_profile = f"{user_identity}\n\n{user_profile}".strip() if (user_identity and user_profile) else (user_identity or user_profile)

    # 构建Agent输入
    agent_input = {
        "messages": history_messages + [{"role": "user", "content": message}],
        "cart": cart,
        "user_id": user_id,
        "summary": summary,
        "user_profile": full_profile,
    }

    # 调用多智能体图
    graph = get_agent_graph()
    result = await graph.ainvoke(agent_input)

    response = result.get("response", "抱歉，处理您的请求时出现了问题。")
    new_cart = result.get("cart", cart)
    intent = result.get("user_intent") or "unknown"
    agent = result.get("active_agent") or "unknown"

    # 保存对话记录
    await chat_repo.save_message(db, user_id, "user", message)
    await chat_repo.save_message(db, user_id, "assistant", response, cart_snapshot=new_cart)

    # 更新记忆缓存
    memory_manager.invalidate_cache(user_id)

    return {
        "response": response,
        "cart": new_cart,
        "intent": intent,
        "agent": agent,
    }
