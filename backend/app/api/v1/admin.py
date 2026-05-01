"""
商家管理 API
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.api.deps import get_db, require_admin
from app.schemas.menu import MenuItemOut, MenuItemCreate, MenuItemUpdate
from app.schemas.order import OrderOut
from app.repositories import menu as menu_repo
from app.models.order import Order
from app.models.order_item import OrderItem
from app.utils.formatters import format_orders_to_txt

router = APIRouter()


@router.get("/admin/menu", response_model=list[MenuItemOut])
async def admin_list_menu(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """商家获取所有商品列表"""
    return await menu_repo.get_all_menu_items(db)


@router.post("/admin/menu", response_model=MenuItemOut)
async def admin_create_menu(
    item: MenuItemCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """商家新增商品"""
    db_item = await menu_repo.create_menu_item(db, item.model_dump())
    return db_item


@router.put("/admin/menu/{item_id}", response_model=MenuItemOut)
async def admin_update_menu(
    item_id: int,
    item: MenuItemUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """商家修改商品"""
    db_item = await menu_repo.update_menu_item(db, item_id, item.model_dump())
    if not db_item:
        raise HTTPException(status_code=404, detail="商品不存在")
    return db_item


@router.delete("/admin/menu/{item_id}")
async def admin_delete_menu(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """商家删除商品"""
    ok = await menu_repo.delete_menu_item(db, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"message": "删除成功"}


@router.get("/admin/orders", response_model=list[OrderOut])
async def admin_list_orders(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """商家获取所有订单（不区分用户）"""
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.menu_item)
        ).order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.get("/admin/orders/export")
async def admin_export_all_orders(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """商家导出所有用户订单为 TXT"""
    result = await db.execute(
        select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.menu_item)
        ).order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    content = format_orders_to_txt(orders, title="全部用户订单列表")
    filename = "all_orders.txt"
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
