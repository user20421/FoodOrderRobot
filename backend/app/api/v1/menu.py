"""
菜单 API
GET /api/v1/menu
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.menu import MenuItemOut
from app.services.menu_service import get_menu

router = APIRouter()


@router.get("/menu", response_model=list[MenuItemOut])
async def list_menu(db: AsyncSession = Depends(get_db)):
    """
    获取所有菜单列表
    """
    items = await get_menu(db)
    return items
