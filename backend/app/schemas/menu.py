"""
菜单相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MenuCategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class MenuItemBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    spicy_level: int = Field(default=0, ge=0, le=5)
    category: str
    tags: Optional[str] = None
    stock: int = Field(default=100, ge=0)


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    spicy_level: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    stock: Optional[int] = None
    is_recommended: Optional[int] = None


class MenuItemOut(MenuItemBase):
    id: int
    is_recommended: int
    sales_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
