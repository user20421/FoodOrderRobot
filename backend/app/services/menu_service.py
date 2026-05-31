"""
菜单服务
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.repositories.menu_repo import menu_category_repo, menu_item_repo
from app.schemas.menu import MenuItemCreate, MenuItemUpdate, MenuItemOut, MenuCategoryOut
from data.menu_data import MENU_ITEMS, MENU_CATEGORIES


async def init_menu_data(db: AsyncSession):
    """初始化菜单数据"""
    # 初始化分类
    for cat_data in MENU_CATEGORIES:
        existing = await menu_category_repo.get_by_name(db, cat_data["name"])
        if not existing:
            await menu_category_repo.create(db, cat_data)

    # 初始化菜品
    count = 0
    for item_data in MENU_ITEMS:
        existing = await menu_item_repo.get_by_name(db, item_data["name"])
        if not existing:
            await menu_item_repo.create(db, item_data)
            count += 1

    print(f"[Init] 菜单数据初始化完成，新增 {count} 道菜品")


async def get_full_menu(db: AsyncSession) -> dict:
    """获取完整菜单"""
    categories = await menu_category_repo.get_all_ordered(db)
    items = await menu_item_repo.get_all(db, limit=200)
    return {
        "categories": [MenuCategoryOut.model_validate(c) for c in categories],
        "items": [MenuItemOut.model_validate(i) for i in items],
    }


async def get_menu_items(db: AsyncSession) -> List[MenuItemOut]:
    """获取所有菜品"""
    items = await menu_item_repo.get_all(db, limit=200)
    return [MenuItemOut.model_validate(i) for i in items]


async def get_recommended_items(db: AsyncSession, limit: int = 8) -> List[MenuItemOut]:
    """获取推荐菜品"""
    items = await menu_item_repo.get_recommended(db, limit)
    return [MenuItemOut.model_validate(i) for i in items]


async def search_menu_items(db: AsyncSession, keyword: str) -> List[MenuItemOut]:
    """搜索菜品"""
    items = await menu_item_repo.search_by_keyword(db, keyword)
    return [MenuItemOut.model_validate(i) for i in items]


async def create_menu_item(db: AsyncSession, data: MenuItemCreate) -> MenuItemOut:
    """创建菜品"""
    item = await menu_item_repo.create(db, data.model_dump())
    return MenuItemOut.model_validate(item)


async def update_menu_item(db: AsyncSession, item_id: int, data: MenuItemUpdate) -> MenuItemOut:
    """更新菜品"""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    item = await menu_item_repo.update(db, item_id, update_data)
    if not item:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("菜品不存在")
    return MenuItemOut.model_validate(item)


async def delete_menu_item(db: AsyncSession, item_id: int) -> bool:
    """删除菜品"""
    return await menu_item_repo.delete(db, item_id)
