"""
项目核心配置
使用 Pydantic Settings 从环境变量和 .env 文件读取配置
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用配置
    app_name: str = "美味餐厅"
    debug: bool = False
    version: str = "3.0.0"

    # 数据库配置 (MySQL)
    database_url: str = "mysql+aiomysql://root:123456@localhost:3306/shuxiangge_bot"

    # MongoDB 配置
    mongodb_url: str = "mongodb://localhost:27017/shuxiangge_bot"

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"

    # 数据存储职责配置
    # MongoDB 作为聊天记录、用户画像、摘要的主存储；Redis 作为记忆缓存。
    # MySQL 中的 ChatHistory 表仅作为可选审计归档，默认关闭以避免三重写入。
    use_mysql_chat_archive: bool = False

    # Chroma 配置
    chroma_persist_dir: str = "./chroma_db"

    # 智谱 AI (Zhipu) 配置
    zhipu_api_key: str = ""  # 从环境变量 ZHIPU_API_KEY 读取

    # 模型配置
    chat_model: str = "glm-4.5-air"  # 对话模型: glm-4.5-air / glm-4-air / glm-4-flash
    embedding_model: str = "embedding-3"  # 智谱 Embedding-3 支持 256/512/1024/2048 维
    embedding_dimensions: int = 512  # 向量维度（必须与 Chroma 集合一致）
    vision_model: str = "glm-4.6v"  # 多模态视觉模型

    # 记忆管理配置
    memory_max_tokens: int = 3000
    memory_summary_trigger_pairs: int = 5
    memory_buffer_size: int = 6

    # RAG 配置
    rag_top_k: int = 3
    rag_multi_query_count: int = 3
    rag_rrf_k: int = 60

    # JWT 配置
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_hours: int = 24

    # 日志配置
    log_level: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
