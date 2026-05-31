"""
商家管理路由
保持与原后端API格式兼容
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.api.deps import check_admin
from app.schemas.menu import MenuItemCreate, MenuItemUpdate, MenuItemOut
from app.schemas.order import OrderOut
from app.services.menu_service import (
    get_menu_items, create_menu_item, update_menu_item, delete_menu_item
)
from app.services.order_service import get_all_orders
from app.utils.formatters import export_order_text

router = APIRouter()


@router.get("/admin/menu", response_model=list[MenuItemOut])
async def admin_list_menu(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """商家获取全部菜品"""
    check_admin(request)
    items = await get_menu_items(db)
    return items


@router.post("/admin/menu", response_model=MenuItemOut)
async def admin_create_menu(
    request: Request,
    data: MenuItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建菜品"""
    check_admin(request)
    item = await create_menu_item(db, data)
    return item


@router.put("/admin/menu/{item_id}", response_model=MenuItemOut)
async def admin_update_menu(
    request: Request,
    item_id: int,
    data: MenuItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新菜品"""
    check_admin(request)
    item = await update_menu_item(db, item_id, data)
    return item


@router.delete("/admin/menu/{item_id}")
async def admin_delete_menu(
    request: Request,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除菜品"""
    check_admin(request)
    success = await delete_menu_item(db, item_id)
    if success:
        return {"message": "删除成功"}
    raise HTTPException(status_code=404, detail="菜品不存在")


@router.get("/admin/orders", response_model=list[OrderOut])
async def admin_list_orders(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """商家获取全部订单"""
    check_admin(request)
    orders = await get_all_orders(db, skip, limit)
    return orders


@router.get("/admin/orders/export")
async def admin_export_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """商家导出全部订单"""
    check_admin(request)
    orders = await get_all_orders(db, limit=1000)
    lines = [export_order_text(o.model_dump()) for o in orders]
    return PlainTextResponse(
        content="\n\n".join(lines),
        headers={"Content-Disposition": "attachment; filename=all_orders.txt"},
    )
