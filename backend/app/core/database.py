"""
数据库配置
SQLAlchemy 2.0 异步引擎和会话
"""
import os
import pymysql
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# ORM 基类
Base = declarative_base()


def _ensure_database_exists():
    """
    同步方式检查并创建数据库（如果不存在）
    """
    # 解析 database_url 获取连接参数
    # 格式: mysql+aiomysql://user:password@host:port/dbname
    url = settings.database_url.replace("mysql+aiomysql://", "mysql://")
    try:
        # 从 settings.database_url 解析 host/port/user/password
        # 简单解析: 去掉前缀后按 @ 分割
        rest = url.replace("mysql://", "")
        creds, host_part = rest.split("@", 1)
        user, password = creds.split(":", 1)
        host_port = host_part.split("/", 1)[0]
        if ":" in host_port:
            host, port_str = host_port.split(":", 1)
            port = int(port_str)
        else:
            host = host_port
            port = 3306

        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",
        )
        with conn.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS ordering_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] 创建数据库时出现问题（可能已存在）: {e}")


def _create_engine():
    _ensure_database_exists()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        future=True,
        pool_recycle=3600,
    )


engine = _create_engine()

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncSession:
    """
    FastAPI Depends 使用的异步数据库会话生成器
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    初始化数据库表结构
    默认仅 create_all（安全），仅在 RECREATE_DB=true 时才会 drop_all
    """
    recreate = os.environ.get("RECREATE_DB", "false").lower() == "true"
    async with engine.begin() as conn:
        if recreate:
            print("[DB] RECREATE_DB=true，正在重建数据库表...")
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
