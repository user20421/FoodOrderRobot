"""
通用响应模型
"""
from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class ListResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: List[T] = []
    total: int = 0


class ErrorResponse(BaseModel):
    code: int = 500
    message: str = "error"
    detail: Optional[str] = None
