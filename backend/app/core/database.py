"""
MySQL 数据库连接管理
使用 SQLAlchemy 2.0 async 模式
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import pymysql

from app.core.config import settings

# 同步创建数据库（如果不存在）
def _ensure_database_exists():
    try:
        sync_url = settings.database_url.replace("mysql+aiomysql://", "mysql+pymysql://")
        from sqlalchemy import create_engine, text
        engine = create_engine(sync_url, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        try:
            parsed = sync_url.replace("mysql+pymysql://", "").split("@")
            credentials = parsed[0]
            host_part = parsed[1]
            user, password = credentials.split(":")
            host_db = host_part.split("/")
            host_port = host_db[0].split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 3306
            db_name = host_db[1] if len(host_db) > 1 else "shuxiangge_bot"

            conn = pymysql.connect(host=host, port=port, user=user, password=password)
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Database] 自动创建数据库失败: {e}")


_ensure_database_exists()

# 异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# ORM 基类
Base = declarative_base()


async def init_db():
    """初始化数据库表结构"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[Database] 数据库表初始化完成")


async def get_db():
    """FastAPI 依赖注入用"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
