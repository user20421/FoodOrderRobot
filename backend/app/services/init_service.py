"""
系统初始化服务
整合所有初始化逻辑
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_service import init_admin_user
from app.services.menu_service import init_menu_data


async def initialize_system(db: AsyncSession):
    """系统初始化入口"""
    await init_menu_data(db)
    await init_admin_user(db)
