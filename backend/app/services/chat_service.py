"""
聊天服务
整合多智能体、记忆管理和RAG
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.logging_config import get_logger
from app.ai.graph.builder import get_agent_graph
from app.ai.memory.manager import MemoryManager
from app.ai.memory.entity_memory import EntityMemory
from app.ai.memory.vector_memory import VectorMemory
from app.repositories.chat_repo import chat_repo
from app.repositories.user_repo import user_repo
from app.services.image_search_service import decode_image_base64, search_dishes_by_image
from app.ai.graph.context import get_top_selling_dishes

from app.services.order_service import get_user_orders, create_order_from_cart, format_order_list


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
    if not result["found"]:
        return "没有找到与图片相关的菜品。"

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
    try:
        image_bytes, mime_type = await decode_image_base64(image_base64)
    except ValueError as e:
        return {"response": str(e), "cart": cart, "intent": "image_search", "agent": "image_search"}

    result = await search_dishes_by_image(image_bytes, mime_type, db)

    if not result["description"]:
        response = "图片识别失败，请尝试上传更清晰的菜品照片。"
    else:
        response = await _format_image_search_response(result)

    # 保存对话记录：用户消息中附加 [图片] 标记
    user_content = message.strip() if message.strip() else "[图片]"
    await chat_repo.save_message(db, user_id, "user", user_content)
    await chat_repo.save_message(db, user_id, "assistant", response, cart_snapshot=cart)

    # 记忆闭环
    memory_manager = get_memory_manager()
    try:
        dialogue_text = f"用户：{user_content}\n机器人：{response}"
        existing_profile = await memory_manager.entity.get_profile(user_id)
        new_entities = await memory_manager.entity.extract_entities(dialogue_text, existing_profile)
        if new_entities:
            await memory_manager.entity.update_profile(user_id, new_entities)
    except Exception as e:
        logger.warning(f"[ChatService] 图片搜菜实体记忆提取失败: {e}")

    try:
        await memory_manager.vector.add_conversation(user_id, "user", user_content)
        await memory_manager.vector.add_conversation(user_id, "assistant", response)
    except Exception as e:
        logger.warning(f"[ChatService] 图片搜菜向量记忆保存失败: {e}")

    memory_manager.invalidate_cache(user_id)

    return {
        "response": response,
        "cart": cart,
        "intent": "image_search",
        "agent": "image_search",
    }


async def _handle_quick_action(db: AsyncSession, user_id: int, message: str, cart: list) -> Optional[dict]:
    """
    处理前端快捷按钮的固定指令，跳过 LLM 和多智能体图直接返回结果。
    这些按钮点击后只是把固定文本发到聊天窗口，没有真实对话语义，不需要意图判断。
    """
    # 1. 查看菜单
    if message == "查看菜单":
        top_dishes = await get_top_selling_dishes(db, 10) if db else []
        if top_dishes:
            lines = []
            for i, dish in enumerate(top_dishes, 1):
                tags = dish.get("tags", "")
                short_desc = "·".join([t.strip() for t in tags.split(",") if t.strip()][:3]) if tags else ""
                if short_desc:
                    lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）- {short_desc}")
                else:
                    lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）")
            response = "本店销量TOP10热门菜品：\n" + "\n".join(lines)
        else:
            response = "本店有丰富多样的菜品供您选择。"
        response += "\n\n[点击浏览完整菜单](/menu)"
        return {"response": response, "cart": cart, "intent": "inquiry", "agent": "inquiry"}

    # 2. 推荐菜品：直接返回销量最高的 5 个菜品
    if message == "有什么推荐的菜品？":
        top_dishes = await get_top_selling_dishes(db, 5) if db else []
        if top_dishes:
            lines = []
            for i, dish in enumerate(top_dishes, 1):
                tags = dish.get("tags", "")
                short_desc = "·".join([t.strip() for t in tags.split(",") if t.strip()][:3]) if tags else ""
                if short_desc:
                    lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）- {short_desc}")
                else:
                    lines.append(f"{i}. {dish['name']}（¥{dish['price']:.0f}）")
            response = "为您推荐本店热销 TOP5 菜品：\n" + "\n".join(lines)
        else:
            response = "本店有很多美味菜品，您可以看看菜单。"
        return {"response": response, "cart": cart, "intent": "recommend", "agent": "recommend"}

    # 3. 查询我的订单
    if message == "查询我的订单":
        orders = await get_user_orders(db, user_id, 20) if db else []
        if orders:
            response = format_order_list(orders, title="您最近的订单如下：")
        else:
            response = "您还没有订单记录。"
        return {"response": response, "cart": cart, "intent": "service", "agent": "service"}

    # 4. 确认下单（快捷按钮）
    if message == "确认下单" and cart:
        try:
            response = await create_order_from_cart(db, user_id, cart)
            return {"response": response, "cart": [], "intent": "order", "agent": "order"}
        except Exception as e:
            logger.warning(f"[ChatService] 快捷确认下单失败，降级到 Agent: {e}")
            return None

    return None


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
    2. 若匹配前端快捷按钮固定指令，直接返回结果
    3. 加载记忆上下文
    4. 调用多智能体图
    5. 保存消息记录
    """
    # 拍照搜菜分支：优先处理图片
    if image_base64:
        return await _process_image_search(db, user_id, message, cart, image_base64)

    # 快捷按钮分支：固定指令直接处理，不走大模型
    quick_result = await _handle_quick_action(db, user_id, message, cart)
    if quick_result:
        await chat_repo.save_message(db, user_id, "user", message, cart_snapshot=quick_result["cart"])
        await chat_repo.save_message(db, user_id, "assistant", quick_result["response"], cart_snapshot=quick_result["cart"])
        try:
            memory_manager = get_memory_manager()
            await memory_manager.vector.add_conversation(user_id, "user", message)
            await memory_manager.vector.add_conversation(user_id, "assistant", quick_result["response"])
            memory_manager.invalidate_cache(user_id)
        except Exception as e:
            logger.warning(f"[ChatService] 快捷操作记忆保存失败: {e}")
        return quick_result

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
        "user_profile": user_identity,
    }

    # 调用多智能体图，将请求级数据库会话通过 config 传入，保证 Graph 内下单/查单与当前请求共享事务上下文
    graph = get_agent_graph()
    result = await graph.ainvoke(agent_input, config={"configurable": {"db_session": db}})

    response = result.get("response", "抱歉，处理您的请求时出现了问题。")
    new_cart = result.get("cart", cart)
    intent = result.get("user_intent") or "unknown"
    agent = result.get("active_agent") or "unknown"

    # 保存对话记录
    await chat_repo.save_message(db, user_id, "user", message)
    await chat_repo.save_message(db, user_id, "assistant", response, cart_snapshot=new_cart)

    # 闭环：提取用户画像 + 保存向量记忆（使用 try/except 隔离，避免影响主流程）
    try:
        dialogue_text = f"用户：{message}\n机器人：{response}"
        existing_profile = await memory_manager.entity.get_profile(user_id)
        new_entities = await memory_manager.entity.extract_entities(dialogue_text, existing_profile)
        if new_entities:
            await memory_manager.entity.update_profile(user_id, new_entities)
    except Exception as e:
        logger.warning(f"[ChatService] 实体记忆提取失败: {e}")

    try:
        await memory_manager.vector.add_conversation(user_id, "user", message)
        await memory_manager.vector.add_conversation(user_id, "assistant", response)
    except Exception as e:
        logger.warning(f"[ChatService] 向量记忆保存失败: {e}")

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
    from app.ai.memory.manager import MemoryManager

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

    # 同时更新记忆缓存，避免用户切换后看不到
    try:
        memory_manager = get_memory_manager()
        await memory_manager.vector.add_conversation(user_id, "assistant", message)
        memory_manager.invalidate_cache(user_id)
    except Exception as e:
        logger.warning(f"[ChatService] 订单完成向量记忆保存失败: {e}")


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
