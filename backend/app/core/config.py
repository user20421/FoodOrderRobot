"""
项目核心配置
使用 Pydantic Settings 从环境变量读取配置
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用配置
    app_name: str = "点餐机器人"
    debug: bool = False

    # 数据库配置 (MySQL)
    database_url: str = "mysql+aiomysql://root:123456@localhost:3306/ordering_bot"

    # 阿里云 DashScope 配置
    dashscope_api_key: str = ""  # 从环境变量 DASHSCOPE_API_KEY 读取

    # 模型配置
    chat_model: str = "qwen-plus"  # 或 qwen-max
    embedding_model: str = "text-embedding-v2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # 允许从环境变量读取，字段名自动转换为大写加下划线
        extra = "ignore"


# 全局配置实例
settings = Settings()
