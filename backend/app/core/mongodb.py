"""
MongoDB 连接管理
使用 Motor 异步驱动，支持优雅降级
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

_mongodb_client: AsyncIOMotorClient | None = None
_mongodb_db = None


async def init_mongodb():
    """初始化 MongoDB 连接"""
    global _mongodb_client, _mongodb_db
    try:
        _mongodb_client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=3000,
        )
        # 验证连接
        await _mongodb_client.admin.command("ping")
        _mongodb_db = _mongodb_client.get_default_database()
        print(f"[MongoDB] 连接成功: {settings.mongodb_url}")
    except Exception as e:
        print(f"[MongoDB] 连接失败（将降级到MySQL）: {e}")
        _mongodb_client = None
        _mongodb_db = None


async def close_mongodb():
    """关闭 MongoDB 连接"""
    global _mongodb_client
    if _mongodb_client:
        _mongodb_client.close()
        _mongodb_client = None
        print("[MongoDB] 连接已关闭")


def get_mongodb_db():
    """获取 MongoDB 数据库实例"""
    return _mongodb_db


def is_mongodb_available() -> bool:
    """检查 MongoDB 是否可用"""
    return _mongodb_db is not None
