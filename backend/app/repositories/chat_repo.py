"""
聊天记录数据访问层
三层存储：MongoDB → In-Memory → MySQL
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.chat import ChatHistory
from app.core.mongodb import get_mongodb_db, is_mongodb_available

# 内存回退存储（按 user_id 分组）
_in_memory_store: Dict[int, List[Dict[str, Any]]] = {}
_MAX_MEMORY_PER_USER = 200


class ChatRepository:
    """聊天仓库：MongoDB 优先，内存次之，MySQL 保底"""

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

        # 1. 尝试 MongoDB
        if is_mongodb_available():
            try:
                mongo_db = get_mongodb_db()
                await mongo_db.chat_messages.insert_one(record)
                return True
            except Exception as e:
                print(f"[ChatRepo] MongoDB 保存失败: {e}")

        # 2. 回退到内存
        _in_memory_store.setdefault(user_id, [])
        _in_memory_store[user_id].append(record)
        if len(_in_memory_store[user_id]) > _MAX_MEMORY_PER_USER:
            _in_memory_store[user_id] = _in_memory_store[user_id][-_MAX_MEMORY_PER_USER:]

        # 3. 同时写入 MySQL（静默）
        try:
            db_obj = ChatHistory(
                user_id=user_id,
                session_id=session_id,
                role=role,
                message=message,
            )
            db.add(db_obj)
            await db.commit()
        except Exception:
            await db.rollback()

        return True

    @staticmethod
    async def get_history(
        db: AsyncSession,
        user_id: int,
        session_id: str = "default",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        # 1. 尝试 MongoDB
        if is_mongodb_available():
            try:
                mongo_db = get_mongodb_db()
                cursor = mongo_db.chat_messages.find(
                    {"user_id": user_id, "session_id": session_id}
                ).sort("created_at", 1).limit(limit)
                records = await cursor.to_list(length=limit)
                return [
                    {
                        "role": r.get("role"),
                        "message": r.get("message"),
                        "created_at": r.get("created_at"),
                    }
                    for r in records
                ]
            except Exception as e:
                print(f"[ChatRepo] MongoDB 读取失败: {e}")

        # 2. 回退到内存
        if user_id in _in_memory_store:
            records = _in_memory_store[user_id][-limit:]
            return [
                {
                    "role": r.get("role"),
                    "message": r.get("message"),
                    "created_at": r.get("created_at"),
                }
                for r in records
            ]

        # 3. 回退到 MySQL
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
        # 清理 MongoDB
        if is_mongodb_available():
            try:
                mongo_db = get_mongodb_db()
                await mongo_db.chat_messages.delete_many(
                    {"user_id": user_id, "session_id": session_id}
                )
            except Exception as e:
                print(f"[ChatRepo] MongoDB 清理失败: {e}")

        # 清理内存
        if user_id in _in_memory_store:
            _in_memory_store[user_id] = []

        # 清理 MySQL
        try:
            from sqlalchemy import delete
            await db.execute(
                delete(ChatHistory).where(
                    ChatHistory.user_id == user_id,
                    ChatHistory.session_id == session_id,
                )
            )
            await db.commit()
        except Exception:
            await db.rollback()


chat_repo = ChatRepository()
