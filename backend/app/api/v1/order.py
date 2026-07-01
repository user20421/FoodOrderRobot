"""
订单路由
保持与原后端API格式兼容
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.core.exceptions import BusinessException, NotFoundException
from app.api.deps import get_current_user
from app.schemas.order import OrderCreate, OrderOut, PaginatedOrdersResponse
from app.services.order_service import (
    create_order,
    get_order_detail,
    get_user_orders_paginated,
    count_user_orders,
)
from app.utils.formatters import export_order_text

router = APIRouter()


@router.post("/order", response_model=OrderOut)
async def place_order(
    data: OrderCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建订单"""
    try:
        order = await create_order(db, current_user["id"], data.items, data.remark)
        return order
    except (BusinessException, NotFoundException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/orders", response_model=PaginatedOrdersResponse)
async def list_orders(
    page: int = 1,
    page_size: int = 10,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户订单列表（分页）"""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    orders, total = await get_user_orders_paginated(db, current_user["id"], page, page_size)
    return {
        "items": orders,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/orders/count")
async def count_orders(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户订单总数"""
    total = await count_user_orders(db, current_user["id"])
    return {"total": total}


@router.get("/order/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取订单详情"""
    order = await get_order_detail(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 非admin只能查看自己的订单
    if current_user["role"] != "admin" and order.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权查看此订单")

    return order


@router.get("/orders/{order_id}/export")
async def export_order(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出订单"""
    order = await get_order_detail(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 非admin只能导出自己的订单
    if current_user["role"] != "admin" and order.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权导出此订单")

    text = export_order_text(order.model_dump())
    return PlainTextResponse(
        content=text,
        headers={"Content-Disposition": f"attachment; filename=order_{order_id}.txt"},
    )


@router.get("/orders/export")
async def export_all_orders(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出所有订单"""
    orders, _ = await get_user_orders_paginated(db, current_user["id"], page=1, page_size=1000)
    lines = [export_order_text(o.model_dump()) for o in orders]
    return PlainTextResponse(
        content="\n\n".join(lines),
        headers={"Content-Disposition": f"attachment; filename=orders_user_{current_user['id']}.txt"},
    )
