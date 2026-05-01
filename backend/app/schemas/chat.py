"""
聊天相关 Pydantic v2 Schema
"""
from pydantic import BaseModel, Field


class CartItem(BaseModel):
    menu_item_id: int
    name: str
    quantity: int = Field(default=1, ge=1, description="数量至少为1")
    unit_price: float = Field(default=0, ge=0, description="单价")


class ChatRequest(BaseModel):
    user_id: int
    message: str = Field(..., min_length=1, description="用户输入消息")
    cart: list[CartItem] | None = None


class ChatResponse(BaseModel):
    response: str
    cart: list[CartItem] | None = None
