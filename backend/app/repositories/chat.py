"""
聊天历史数据访问层
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_history import ChatHistory


async def save_chat_message(db: AsyncSession, user_id: int, role: str, message: str):
    record = ChatHistory(user_id=user_id, role=role, message=message)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_chat_history_by_user(db: AsyncSession, user_id: int, limit: int = 20):
    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    # 按时间正序返回
    return list(reversed(records))
