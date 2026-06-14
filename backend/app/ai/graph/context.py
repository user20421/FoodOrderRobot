"""
Graph 节点所需的上下文查询与购物车富化工具
"""
from typing import List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import MenuItem
from app.repositories.menu_repo import menu_item_repo
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def get_top_selling_dishes(db: AsyncSession, limit: int = 10) -> List[Dict]:
    """查询销量最高的菜品"""
    try:
        result = await db.execute(
            select(MenuItem)
            .order_by(MenuItem.sales_count.desc())
            .limit(limit)
        )
        items = result.scalars().all()
        return [
            {
                "name": item.name,
                "price": float(item.price),
                "description": item.description or "",
                "tags": item.tags or "",
                "sales_count": item.sales_count or 0,
                "category": item.category,
            }
            for item in items
        ]
    except Exception as e:
        logger.warning(f"[TopSelling] 查询失败: {e}")
        return []


async def enrich_cart(db: AsyncSession, cart: List[Dict]) -> List[Dict]:
    """补充购物车中的价格、menu_item_id等信息，并合并同名项"""
    if not cart:
        return cart

    try:
        result = await db.execute(select(MenuItem))
        all_menu_items = list(result.scalars().all())

        # 第一步：补充信息
        enriched = []
        for item in cart:
            name = item.get("name", "")
            menu_item = await menu_item_repo.get_by_name(db, name)

            if not menu_item and name:
                for mi in all_menu_items:
                    if name in mi.name or mi.name in name:
                        menu_item = mi
                        break

            if menu_item:
                enriched.append({
                    "menu_item_id": menu_item.id,
                    "name": menu_item.name,
                    "quantity": item.get("quantity", 1),
                    "unit_price": float(menu_item.price),
                })
            else:
                enriched.append(dict(item))

        # 第二步：合并同名项（按 menu_item_id 或 name）
        merged = {}
        for item in enriched:
            key = item.get("menu_item_id") or item.get("name", "")
            if not key:
                continue
            if key in merged:
                merged[key]["quantity"] += item.get("quantity", 1)
            else:
                merged[key] = dict(item)

        return list(merged.values())
    except Exception as e:
        logger.warning(f"[CartEnrich] 补充购物车信息失败: {e}")
        return cart
