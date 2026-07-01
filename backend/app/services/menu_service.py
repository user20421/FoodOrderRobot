"""
菜单服务
"""
import json
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.repositories.menu_repo import menu_category_repo, menu_item_repo
from app.models.menu import MenuItem
from app.schemas.menu import MenuItemCreate, MenuItemUpdate, MenuItemOut, MenuCategoryOut
from app.core.redis import get_redis, is_redis_available
from app.core.logging_config import get_logger
from data.menu_data import MENU_ITEMS, MENU_CATEGORIES

logger = get_logger(__name__)

_MENU_CACHE_KEY = "menu:all"
_MENU_CACHE_TTL = 600  # 10 分钟


def _menu_items_to_json(items: List[MenuItemOut]) -> str:
    return json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False)


def _menu_items_from_json(raw: str) -> List[MenuItemOut]:
    data = json.loads(raw)
    return [MenuItemOut.model_validate(item) for item in data]


async def _invalidate_menu_cache(delay_second_delete: bool = True):
    """
    使菜单缓存失效。
    采用 Cache-Aside + 延迟双删策略，减少并发下的脏读概率。
    """
    if not is_redis_available():
        return
    try:
        redis_client = get_redis()
        await redis_client.delete(_MENU_CACHE_KEY)
        if delay_second_delete:
            # 异步延迟再次删除，期间旧缓存可能被回填，第二次删除保证一致性
            asyncio.create_task(_delayed_cache_delete(_MENU_CACHE_KEY, delay_seconds=0.5))
    except Exception as e:
        logger.warning(f"[MenuService] 清除菜单缓存失败: {e}")


async def _delayed_cache_delete(key: str, delay_seconds: float):
    """延迟删除缓存"""
    await asyncio.sleep(delay_seconds)
    try:
        redis_client = get_redis()
        await redis_client.delete(key)
    except Exception as e:
        logger.warning(f"[MenuService] 延迟清除菜单缓存失败: {e}")


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

    await db.commit()
    logger.info(f"[Init] 菜单数据初始化完成，新增 {count} 道菜品")


async def get_full_menu(db: AsyncSession) -> dict:
    """获取完整菜单"""
    categories = await menu_category_repo.get_all_ordered(db)
    items = await get_menu_items(db)
    return {
        "categories": [MenuCategoryOut.model_validate(c) for c in categories],
        "items": items,
    }


async def count_menu_items(db: AsyncSession) -> int:
    """获取菜品总数"""
    return await menu_item_repo.count(db)


async def get_menu_items(db: AsyncSession) -> List[MenuItemOut]:
    """获取所有菜品（带 Redis 缓存）"""
    # 1. 尝试 Redis 缓存
    if is_redis_available():
        try:
            redis_client = get_redis()
            cached = await redis_client.get(_MENU_CACHE_KEY)
            if cached:
                return _menu_items_from_json(cached)
        except Exception as e:
            logger.warning(f"[MenuService] 读取菜单缓存失败: {e}")

    # 2. 查询 MySQL
    items = await menu_item_repo.get_all(db, limit=200)
    result = [MenuItemOut.model_validate(i) for i in items]

    # 3. 写入 Redis 缓存
    if is_redis_available():
        try:
            redis_client = get_redis()
            await redis_client.set(_MENU_CACHE_KEY, _menu_items_to_json(result), ex=_MENU_CACHE_TTL)
        except Exception as e:
            logger.warning(f"[MenuService] 写入菜单缓存失败: {e}")

    return result


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
    await db.commit()
    await _invalidate_menu_cache()
    return MenuItemOut.model_validate(item)


async def update_menu_item(db: AsyncSession, item_id: int, data: MenuItemUpdate) -> MenuItemOut:
    """更新菜品"""
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    item = await menu_item_repo.update(db, item_id, update_data)
    if not item:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("菜品不存在")
    await db.commit()
    await _invalidate_menu_cache()
    return MenuItemOut.model_validate(item)


async def delete_menu_item(db: AsyncSession, item_id: int) -> bool:
    """删除菜品"""
    result = await menu_item_repo.delete(db, item_id)
    if result:
        await db.commit()
        await _invalidate_menu_cache()
    return result


async def get_top_selling_items(db: AsyncSession, limit: int = 5) -> List[MenuItemOut]:
    """按销量返回热销菜品（供 Agent 推荐 fallback 使用）。"""
    result = await db.execute(select(MenuItem).order_by(MenuItem.sales_count.desc()).limit(limit))
    return [MenuItemOut.model_validate(i) for i in result.scalars().all()]


async def get_item_by_name(db: AsyncSession, name: str) -> Optional[MenuItemOut]:
    """按名称精确或模糊匹配单个菜品（供 Agent 工具使用）。"""
    item = await menu_item_repo.get_by_name(db, name)
    if item:
        return MenuItemOut.model_validate(item)
    # 模糊匹配
    items = await menu_item_repo.search_by_keyword(db, name)
    if items:
        return MenuItemOut.model_validate(items[0])
    return None
