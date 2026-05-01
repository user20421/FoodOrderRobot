"""
菜单业务服务
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import menu as menu_repo
from app.mock.data import MENU_ITEMS


async def init_menu_data(db: AsyncSession):
    """
    如果菜单表为空，则初始化模拟数据，并给每个菜品设置默认库存
    """
    items = await menu_repo.get_all_menu_items(db)
    if not items:
        for item in MENU_ITEMS:
            item["stock"] = 100
        await menu_repo.bulk_create_menu_items(db, MENU_ITEMS)
        return True
    return False


async def get_menu(db: AsyncSession):
    return await menu_repo.get_all_menu_items(db)
