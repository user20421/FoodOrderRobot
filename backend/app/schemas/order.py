"""
订单相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CartItem(BaseModel):
    menu_item_id: int
    name: str
    quantity: int = Field(..., gt=0)
    unit_price: float


class OrderItemOut(BaseModel):
    id: int
    menu_item_id: int
    name: str
    quantity: int
    unit_price: float
    subtotal: float

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    items: List[CartItem]
    remark: Optional[str] = None


class OrderOut(BaseModel):
    id: int
    user_id: int
    status: str
    total_price: float
    remark: Optional[str] = None
    items: List[OrderItemOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderExport(BaseModel):
    id: int
    status: str
    total_price: float
    created_at: datetime
    item_summary: str
