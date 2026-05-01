"""
菜单相关 Pydantic v2 Schema
"""
from pydantic import BaseModel, ConfigDict, Field


class MenuItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="菜品名称")
    description: str | None = Field(default=None, max_length=500, description="菜品描述")
    price: float = Field(..., gt=0, description="价格必须大于0")
    spicy_level: int = Field(default=0, ge=0, le=5, description="辣度 0-5")
    category: str | None = Field(default=None, max_length=50, description="分类")
    tags: str | None = Field(default=None, max_length=200, description="标签，逗号分隔")
    stock: int = Field(default=100, ge=0, description="库存数量")


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemOut(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class MenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    price: float | None = Field(default=None, gt=0)
    spicy_level: int | None = Field(default=None, ge=0, le=5)
    category: str | None = Field(default=None, max_length=50)
    tags: str | None = Field(default=None, max_length=200)
    stock: int | None = Field(default=None, ge=0)
