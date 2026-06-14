"""
商家管理路由
保持与原后端API格式兼容
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import require_admin
from app.schemas.menu import MenuItemCreate, MenuItemUpdate, MenuItemOut
from app.schemas.order import OrderOut
from app.services.menu_service import (
    get_menu_items, create_menu_item, update_menu_item, delete_menu_item, count_menu_items
)
from app.services.order_service import get_all_orders, get_dashboard_stats, get_pending_orders, complete_order
from app.utils.formatters import export_order_text

router = APIRouter()


@router.get("/admin/dashboard")
async def admin_dashboard(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """商家仪表盘统计数据"""
    stats = await get_dashboard_stats(db)
    stats["total_items"] = await count_menu_items(db)
    return stats


@router.get("/admin/menu", response_model=list[MenuItemOut])
async def admin_list_menu(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """商家获取全部菜品"""
    items = await get_menu_items(db)
    return items


@router.post("/admin/menu", response_model=MenuItemOut)
async def admin_create_menu(
    data: MenuItemCreate,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建菜品"""
    item = await create_menu_item(db, data)
    return item


@router.put("/admin/menu/{item_id}", response_model=MenuItemOut)
async def admin_update_menu(
    item_id: int,
    data: MenuItemUpdate,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新菜品"""
    item = await update_menu_item(db, item_id, data)
    return item


@router.delete("/admin/menu/{item_id}")
async def admin_delete_menu(
    item_id: int,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除菜品"""
    success = await delete_menu_item(db, item_id)
    if success:
        return {"message": "删除成功"}
    raise HTTPException(status_code=404, detail="菜品不存在")


@router.get("/admin/orders", response_model=list[OrderOut])
async def admin_list_orders(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """商家获取全部订单"""
    skip = max(0, skip)
    limit = max(1, min(limit, 100))
    orders = await get_all_orders(db, skip, limit)
    return orders


@router.get("/admin/orders/pending", response_model=list[OrderOut])
async def admin_list_pending_orders(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """商家获取待处理订单（未完成的订单）"""
    orders = await get_pending_orders(db)
    return orders


@router.post("/admin/orders/{order_id}/complete")
async def admin_complete_order(
    order_id: int,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """商家完成订单制作，并通知用户"""
    order = await complete_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"message": "订单已完成", "order": order}


@router.get("/admin/orders/export")
async def admin_export_orders(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """商家导出全部订单"""
    orders = await get_all_orders(db, limit=1000)
    lines = [export_order_text(o.model_dump()) for o in orders]
    return PlainTextResponse(
        content="\n\n".join(lines),
        headers={"Content-Disposition": "attachment; filename=all_orders.txt"},
    )
