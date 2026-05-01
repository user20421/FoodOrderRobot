"""
菜单数据访问层
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu_item import MenuItem


async def get_all_menu_items(db: AsyncSession):
    result = await db.execute(select(MenuItem))
    return result.scalars().all()


async def get_menu_item_by_id(db: AsyncSession, item_id: int):
    result = await db.execute(select(MenuItem).where(MenuItem.id == item_id))
    return result.scalar_one_or_none()


async def create_menu_item(db: AsyncSession, item_data: dict):
    db_item = MenuItem(**item_data)
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item


async def bulk_create_menu_items(db: AsyncSession, items: list[dict]):
    db_items = [MenuItem(**item) for item in items]
    db.add_all(db_items)
    await db.commit()
    return db_items


async def update_menu_item(db: AsyncSession, item_id: int, item_data: dict):
    item = await get_menu_item_by_id(db, item_id)
    if not item:
        return None
    for key, value in item_data.items():
        if value is not None and hasattr(item, key):
            setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_menu_item(db: AsyncSession, item_id: int):
    item = await get_menu_item_by_id(db, item_id)
    if not item:
        return False
    await db.delete(item)
    await db.commit()
    return True
