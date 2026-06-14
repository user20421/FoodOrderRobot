"""
Redis 连接管理
使用 redis.asyncio 异步客户端，支持优雅降级
"""
from typing import Optional
from redis.asyncio import Redis
from app.core.config import settings

_redis_client: Optional[Redis] = None


async def init_redis() -> None:
    """初始化 Redis 连接"""
    global _redis_client
    try:
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_keepalive=True,
        )
        await _redis_client.ping()
        print(f"[Redis] 连接成功: {settings.redis_url}")
    except Exception as e:
        print(f"[Redis] 连接失败（将降级为不可用）: {e}")
        _redis_client = None


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        print("[Redis] 连接已关闭")


def get_redis() -> Optional[Redis]:
    """获取 Redis 客户端实例"""
    return _redis_client


def is_redis_available() -> bool:
    """检查 Redis 是否可用"""
    return _redis_client is not None
