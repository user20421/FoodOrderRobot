"""
订单相关 Pydantic v2 Schema
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1, description="数量至少为1")


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    quantity: int
    unit_price: float
    menu_item_name: str = ""


class OrderCreate(BaseModel):
    user_id: int
    items: list[OrderItemCreate]


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    total_price: float
    created_at: datetime
    items: list[OrderItemOut] = Field(default_factory=list)
