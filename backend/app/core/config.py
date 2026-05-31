"""
项目核心配置
使用 Pydantic Settings 从环境变量和 .env 文件读取配置
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用配置
    app_name: str = "智能点餐机器人"
    debug: bool = False
    version: str = "3.0.0"

    # 数据库配置 (MySQL)
    database_url: str = "mysql+aiomysql://root:123456@localhost:3306/shuxiangge_bot"

    # MongoDB 配置
    mongodb_url: str = "mongodb://localhost:27017/shuxiangge_bot"

    # Chroma 配置
    chroma_persist_dir: str = "./chroma_db"

    # 阿里云 DashScope 配置
    dashscope_api_key: str = ""  # 从环境变量 DASHSCOPE_API_KEY 读取

    # 模型配置
    chat_model: str = "qwen-max"  # qwen-max / qwen-turbo / qwen3-max
    embedding_model: str = "text-embedding-v3"
    vision_model: str = "qwen-vl-plus"  # 多模态视觉模型: qwen-vl-plus / qwen-vl-max / qwen3.5-omni-plus

    # 记忆管理配置
    memory_max_tokens: int = 3000
    memory_summary_trigger_pairs: int = 5
    memory_buffer_size: int = 6

    # RAG 配置
    rag_top_k: int = 3
    rag_multi_query_count: int = 3
    rag_rrf_k: int = 60

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
