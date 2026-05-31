"""
菜单路由
保持与原后端API格式兼容
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.menu import MenuItemOut
from app.services.menu_service import get_menu_items

router = APIRouter()


@router.get("/menu", response_model=list[MenuItemOut])
async def get_menu(db: AsyncSession = Depends(get_db)):
    """获取完整菜单"""
    items = await get_menu_items(db)
    return items
