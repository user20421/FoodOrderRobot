"""
订单 API
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.schemas.order import OrderCreate, OrderOut
from app.services.order_service import create_order, get_order
from app.repositories.order import get_orders_by_user, get_order_by_id
from app.utils.formatters import format_order_to_txt, format_orders_to_txt

router = APIRouter()


@router.post("/order", response_model=OrderOut)
async def place_order(order_in: OrderCreate, db: AsyncSession = Depends(get_db)):
    """创建订单"""
    order = await create_order(db, order_in.user_id, [item.model_dump() for item in order_in.items])
    if isinstance(order, dict) and order.get("error"):
        raise HTTPException(status_code=400, detail=order["error"])
    if not order:
        raise HTTPException(status_code=400, detail="创建订单失败，菜品不存在")
    return order


@router.get("/order/{order_id}", response_model=OrderOut)
async def read_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """查询订单详情"""
    order = await get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    查询用户订单列表
    只能查询当前登录用户自己的订单
    """
    if current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只能查看自己的订单")
    orders = await get_orders_by_user(db, user_id)
    return orders


@router.get("/orders/{order_id}/export")
async def export_single_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """导出单次订单为 TXT"""
    order = await get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    # 权限校验：只能导出自己的订单（管理员除外）
    if current_user["id"] != order.user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只能导出自己的订单")
    content = format_order_to_txt(order)
    filename = f"order_{order_id}.txt"
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/orders/export")
async def export_all_orders(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """导出用户全部订单为 TXT"""
    if current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只能导出自己的订单")
    orders = await get_orders_by_user(db, user_id)
    content = format_orders_to_txt(orders, title=f"用户 {user_id} 的订单列表")
    filename = f"orders_user_{user_id}.txt"
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
