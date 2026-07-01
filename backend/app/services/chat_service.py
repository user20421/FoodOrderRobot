"""
聊天服务
整合多智能体、记忆管理
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.logging_config import get_logger
from app.ai.graph.builder import get_agent_graph
from app.ai.memory.manager import MemoryManager
from app.ai.routing import try_fast_path
from app.repositories.chat_repo import chat_repo
from app.repositories.user_repo import user_repo
from app.services.image_search_service import decode_image_base64, search_dishes_by_image


logger = get_logger(__name__)


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


async def _format_image_search_response(result: dict) -> str:
    """把图片搜菜结果格式化为最终回复文本。"""
    description = result.get("description", "")
    if not description:
        return "图片识别失败，请尝试上传更清晰的菜品照片。"

    if not result["found"]:
        # 友好提示：说明识别到了什么，但本店没有
        return (
            f"图片看起来是：{description}\n"
            f"抱歉，本店菜单中没有找到与这道菜相同或非常相似的菜品。"
        )

    menu_items = result["menu_items"]
    matches = result["matches"]
    lines = [f"图片看起来是：{description}", "根据图片特征，本店有以下相似菜品："]
    for m in matches[:3]:
        name = m.get("name", "")
        reason = m.get("reason", "")
        item = next((i for i in menu_items if i["name"] == name), None)
        if item:
            lines.append(f"• {item['name']}（¥{item['price']:.0f}）- {reason}")
        else:
            lines.append(f"• {name} - {reason}")
    return "\n".join(lines)


async def _process_image_search(
    db: AsyncSession,
    user_id: int,
    message: str,
    cart: list,
    image_base64: str,
) -> dict:
    """
    处理"拍照搜菜"分支：
    多模态模型生成图像摘要 → LLM 匹配菜单 → 格式化推荐。
    同时保存用户消息和助手回复到聊天记录。
    """
    response = "图片处理失败，请稍后重试或换一张图片。"
    try:
        image_bytes, mime_type = await decode_image_base64(image_base64)
        result = await search_dishes_by_image(image_bytes, mime_type, db)
        if not result["description"]:
            response = "图片识别失败，请尝试上传更清晰的菜品照片。"
        else:
            response = await _format_image_search_response(result)
    except ValueError as e:
        response = str(e)
    except Exception as e:
        logger.exception(f"[ChatService] 图片搜菜处理异常: {e}")
        response = "图片处理时出现问题，请稍后重试。"

    # 保存对话记录：用户消息中附加 [图片] 标记
    user_content = message.strip() if message.strip() else "[图片]"
    await chat_repo.save_message(db, user_id, "user", user_content)
    await chat_repo.save_message(db, user_id, "assistant", response, cart_snapshot=cart)

    return {
        "response": response,
        "cart": cart,
        "intent": "image_search",
        "agent": "image_search",
    }


async def _process_chat_core(
    db: AsyncSession,
    user_id: int,
    message: str,
    cart: list,
    image_base64: Optional[str] = None,
) -> dict:
    """
    处理聊天消息的核心逻辑（不管理事务，调用方必须保证所需 DB 会话状态）。
    1. 若携带图片，走拍照搜菜分支
    2. 尝试规则快速通道（不调用 LLM）
    3. 加载记忆上下文
    4. 调用多智能体图
    5. 保存消息记录
    """
    # 拍照搜菜分支：优先处理图片
    if image_base64:
        return await _process_image_search(db, user_id, message, cart, image_base64)

    # 快速通道：高频、语义明确的意图直接由传统函数处理
    fast_result = await try_fast_path(message, cart, db, user_id)
    if fast_result:
        await chat_repo.save_message(db, user_id, "user", message, cart_snapshot=fast_result["cart"])
        await chat_repo.save_message(db, user_id, "assistant", fast_result["response"], cart_snapshot=fast_result["cart"])
        return fast_result

    memory_manager = get_memory_manager()

    # 加载对话上下文
    history_messages, summary = await memory_manager.get_conversation_context(user_id)

    # 获取用户身份信息（用户名等），不再注入忌口/饮食限制等用户画像，避免干扰正常下单
    user_identity = await _get_user_identity(db, user_id)

    # 构建Agent输入
    agent_input = {
        "messages": history_messages + [{"role": "user", "content": message}],
        "cart": cart,
        "user_id": user_id,
        "summary": summary,
        "user_identity": user_identity,
    }

    # 调用多智能体图，将请求级数据库会话通过 config 传入，保证 Graph 内下单/查单与当前请求共享事务上下文
    graph = get_agent_graph()
    result = await graph.ainvoke(agent_input, config={"configurable": {"db_session": db}})

    response = result.get("response", "抱歉，处理您的请求时出现了问题。")
    new_cart = result.get("cart", cart)
    intent = result.get("intent") or "unknown"
    agent = result.get("current_agent") or "unknown"

    # 保存对话记录
    await chat_repo.save_message(db, user_id, "user", message)
    await chat_repo.save_message(db, user_id, "assistant", response, cart_snapshot=new_cart)

    # 更新短期记忆缓存
    memory_manager.add_to_buffer(user_id, "user", message)
    memory_manager.add_to_buffer(user_id, "assistant", response)

    # 更新记忆缓存
    memory_manager.invalidate_cache(user_id)

    return {
        "response": response,
        "cart": new_cart,
        "intent": intent,
        "agent": agent,
    }


async def notify_user_order_completed(user_id: int, order_id: int):
    """
    订单完成后，向用户聊天窗口推送一条系统通知消息。
    消息会保存到聊天记录，用户进入聊天页即可看到。
    """
    from app.core.database import AsyncSessionLocal

    message = (
        f"🎉 您好，您的订单 **#{order_id}** 已完成制作！\n"
        f"感谢您的订购，欢迎再次光临。"
    )

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                await chat_repo.save_message(db, user_id, "assistant", message)
        except Exception as e:
            logger.warning(f"[ChatService] 保存订单完成通知失败: {e}")


async def process_chat(
    db: AsyncSession,
    user_id: int,
    message: str,
    cart: list = None,
    image_base64: Optional[str] = None,
) -> dict:
    """
    处理聊天消息。
    如果调用方已经开启了事务，则复用该事务；否则在本函数内新建事务，
    保证聊天记录的 MySQL 写入与 Agent 内的下单/查单在同一事务边界内。
    """
    cart = cart or []

    # 为了保证聊天记录的 MySQL 写入与 Agent 内的下单/查单在同一事务边界内，
    # 我们在任何 MySQL 查询之前显式开启事务。
    if db.in_transaction():
        return await _process_chat_core(db, user_id, message, cart, image_base64)
    else:
        async with db.begin():
            return await _process_chat_core(db, user_id, message, cart, image_base64)
