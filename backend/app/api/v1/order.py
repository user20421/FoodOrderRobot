"""
订单路由
保持与原后端API格式兼容
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.core.exceptions import BusinessException, NotFoundException
from app.schemas.order import OrderCreate, OrderOut, CartItem
from app.services.order_service import create_order, get_user_orders, get_order_detail
from app.utils.formatters import export_order_text

router = APIRouter()


@router.post("/order", response_model=OrderOut)
async def place_order(
    request: Request,
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建订单"""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        order = await create_order(db, int(user_id), data.items, data.remark)
        return order
    except (BusinessException, NotFoundException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    request: Request,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """获取用户订单列表"""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    orders = await get_user_orders(db, int(user_id), limit)
    return orders


@router.get("/order/{order_id}", response_model=OrderOut)
async def get_order(
    request: Request,
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取订单详情"""
    user_id = request.headers.get("X-User-ID")
    user_role = request.headers.get("X-User-Role", "customer")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    order = await get_order_detail(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 非admin只能查看自己的订单
    if user_role != "admin" and order.user_id != int(user_id):
        raise HTTPException(status_code=403, detail="无权查看此订单")
    
    return order


@router.get("/orders/{order_id}/export")
async def export_order(
    request: Request,
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """导出订单"""
    user_id = request.headers.get("X-User-ID")
    user_role = request.headers.get("X-User-Role", "customer")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    order = await get_order_detail(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 非admin只能导出自己的订单
    if user_role != "admin" and order.user_id != int(user_id):
        raise HTTPException(status_code=403, detail="无权导出此订单")

    text = export_order_text(order.model_dump())
    return PlainTextResponse(
        content=text,
        headers={"Content-Disposition": f"attachment; filename=order_{order_id}.txt"},
    )


@router.get("/orders/export")
async def export_all_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """导出所有订单"""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    orders = await get_user_orders(db, int(user_id), limit=100)
    lines = [export_order_text(o.model_dump()) for o in orders]
    return PlainTextResponse(
        content="\n\n".join(lines),
        headers={"Content-Disposition": f"attachment; filename=orders_user_{user_id}.txt"},
    )
