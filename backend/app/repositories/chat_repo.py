"""
聊天记录数据访问层

职责划分：
- MongoDB（Beanie）：聊天记录主存储，持久化保存所有对话。
- Redis：短期记忆缓存，加速最近对话的读取。
- MySQL（ChatHistory）：可选审计归档，默认关闭，可通过配置开启。
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import json

from app.models.chat import ChatHistory
from app.core.mongodb import is_mongodb_available, is_beanie_initialized
from app.core.redis import get_redis, is_redis_available
from app.core.config import settings
from app.documents.chat import ChatMessageDocument

_MAX_MEMORY_PER_USER = 200


def _redis_key(user_id: int, session_id: str) -> str:
    return f"chat:memory:{user_id}:{session_id}"


class ChatRepository:
    """聊天仓库：MongoDB 主存 + Redis 缓存 + MySQL 可选归档"""

    @staticmethod
    async def save_message(
        db: AsyncSession,
        user_id: int,
        role: str,
        message: str,
        session_id: str = "default",
        cart_snapshot: Optional[list] = None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "message": message,
            "cart_snapshot": cart_snapshot,
            "created_at": now,
        }

        # 1. 主存：MongoDB (Beanie)
        if is_mongodb_available() and is_beanie_initialized():
            try:
                await ChatMessageDocument(**record).insert()
            except Exception as e:
                print(f"[ChatRepo] MongoDB 保存失败: {e}")

        # 2. 缓存：Redis（LRU 列表，加速近期读取）
        if is_redis_available():
            try:
                redis_client = get_redis()
                key = _redis_key(user_id, session_id)
                await redis_client.lpush(key, json.dumps(record, default=str))
                await redis_client.ltrim(key, 0, _MAX_MEMORY_PER_USER - 1)
                await redis_client.expire(key, 86400)  # 24小时过期
            except Exception as e:
                print(f"[ChatRepo] Redis 保存失败: {e}")

        # 3. 可选归档：MySQL（由调用方控制事务提交）
        if settings.use_mysql_chat_archive:
            try:
                db_obj = ChatHistory(
                    user_id=user_id,
                    session_id=session_id,
                    role=role,
                    message=message,
                )
                db.add(db_obj)
                # 注意：不再自行 commit，由 Service/API 层统一控制事务
            except Exception as e:
                print(f"[ChatRepo] MySQL 归档写入失败: {e}")

        return True

    @staticmethod
    async def get_history(
        db: AsyncSession,
        user_id: int,
        session_id: str = "default",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        # 1. 优先读 Redis 缓存
        if is_redis_available():
            try:
                redis_client = get_redis()
                key = _redis_key(user_id, session_id)
                cached_count = await redis_client.llen(key)
                if cached_count >= limit:
                    raw_items = await redis_client.lrange(key, 0, limit - 1)
                    records = []
                    for raw in reversed(raw_items):  # lpush 后最新在左侧，反转按时间正序
                        item = json.loads(raw)
                        records.append({
                            "role": item.get("role"),
                            "message": item.get("message"),
                            "created_at": item.get("created_at"),
                        })
                    return records
            except Exception as e:
                print(f"[ChatRepo] Redis 读取失败: {e}")

        # 2. 回退到 MongoDB (Beanie) 主存
        if is_mongodb_available() and is_beanie_initialized():
            try:
                docs = await ChatMessageDocument.find(
                    ChatMessageDocument.user_id == user_id,
                    ChatMessageDocument.session_id == session_id,
                ).sort(+ChatMessageDocument.created_at).limit(limit).to_list()
                records = [
                    {
                        "role": d.role,
                        "message": d.message,
                        "created_at": d.created_at,
                    }
                    for d in docs
                ]
                # 回填 Redis 缓存
                if is_redis_available() and records:
                    try:
                        redis_client = get_redis()
                        key = _redis_key(user_id, session_id)
                        pipe = redis_client.pipeline()
                        pipe.delete(key)
                        for r in records:
                            pipe.rpush(key, json.dumps(r, default=str))
                        pipe.expire(key, 86400)
                        await pipe.execute()
                    except Exception as e:
                        print(f"[ChatRepo] Redis 回填失败: {e}")
                return records
            except Exception as e:
                print(f"[ChatRepo] MongoDB 读取失败: {e}")

        # 3. 最后回退到 MySQL（仅当开启归档且 MongoDB 不可用时）
        if settings.use_mysql_chat_archive:
            try:
                result = await db.execute(
                    select(ChatHistory)
                    .where(ChatHistory.user_id == user_id, ChatHistory.session_id == session_id)
                    .order_by(desc(ChatHistory.created_at))
                    .limit(limit)
                )
                records = result.scalars().all()
                return [
                    {
                        "role": r.role,
                        "message": r.message,
                        "created_at": r.created_at,
                    }
                    for r in reversed(records)
                ]
            except Exception as e:
                print(f"[ChatRepo] MySQL 读取失败: {e}")

        return []

    @staticmethod
    async def clear_history(db: AsyncSession, user_id: int, session_id: str = "default"):
        # 清理 MongoDB (Beanie)
        if is_mongodb_available() and is_beanie_initialized():
            try:
                await ChatMessageDocument.find(
                    ChatMessageDocument.user_id == user_id,
                    ChatMessageDocument.session_id == session_id,
                ).delete()
            except Exception as e:
                print(f"[ChatRepo] MongoDB 清理失败: {e}")

        # 清理 Redis
        if is_redis_available():
            try:
                redis_client = get_redis()
                key = _redis_key(user_id, session_id)
                await redis_client.delete(key)
            except Exception as e:
                print(f"[ChatRepo] Redis 清理失败: {e}")

        # 清理 MySQL（可选归档）
        if settings.use_mysql_chat_archive:
            try:
                result = await db.execute(
                    select(ChatHistory)
                    .where(ChatHistory.user_id == user_id, ChatHistory.session_id == session_id)
                )
                records = result.scalars().all()
                for r in records:
                    await db.delete(r)
                # 注意：由调用方控制 commit
            except Exception as e:
                print(f"[ChatRepo] MySQL 清理失败: {e}")


chat_repo = ChatRepository()
