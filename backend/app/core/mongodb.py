"""
MongoDB 连接管理
使用 Motor 异步驱动 + Beanie ODM，支持优雅降级
"""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.documents import ChatMessageDocument, ConversationSummaryDocument

_mongodb_client: AsyncIOMotorClient | None = None
_mongodb_db = None
_beanie_initialized: bool = False


async def init_mongodb():
    """初始化 MongoDB 连接与 Beanie ODM"""
    global _mongodb_client, _mongodb_db, _beanie_initialized
    try:
        _mongodb_client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=3000,
        )
        # 验证连接
        await _mongodb_client.admin.command("ping")
        _mongodb_db = _mongodb_client.get_default_database()

        # 兼容 Beanie 2.1.0 + Motor 3.7.x：
        # Beanie 会调用 database.client.append_metadata()，但 Motor 的 AsyncIOMotorClient
        # 把任意属性访问都当成 database 名称，导致 append_metadata 被解析为 MotorDatabase。
        # 此处通过 monkey-patch 将调用委托给底层的 PyMongo MongoClient。
        if not hasattr(AsyncIOMotorClient, "append_metadata"):
            def _append_metadata(self, metadata):
                return self.delegate.append_metadata(metadata)
            AsyncIOMotorClient.append_metadata = _append_metadata

        # 初始化 Beanie ODM
        await init_beanie(
            database=_mongodb_db,
            document_models=[
                ChatMessageDocument,
                ConversationSummaryDocument,
            ],
        )
        _beanie_initialized = True
        print(f"[MongoDB] 连接成功: {settings.mongodb_url}")
    except Exception as e:
        print(f"[MongoDB] 连接失败（将降级到MySQL/内存）: {e}")
        _mongodb_client = None
        _mongodb_db = None
        _beanie_initialized = False


async def close_mongodb():
    """关闭 MongoDB 连接"""
    global _mongodb_client
    if _mongodb_client:
        _mongodb_client.close()
        _mongodb_client = None
        print("[MongoDB] 连接已关闭")


def get_mongodb_db():
    """获取 MongoDB 数据库实例（原始 Motor 兼容）"""
    return _mongodb_db


def is_mongodb_available() -> bool:
    """检查 MongoDB 是否可用"""
    return _mongodb_db is not None


def is_beanie_initialized() -> bool:
    """检查 Beanie 是否已完成初始化"""
    return _beanie_initialized
