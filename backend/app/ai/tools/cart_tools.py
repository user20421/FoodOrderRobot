"""
购物车相关工具
"""
from typing import Optional
from langchain_core.tools import tool


@tool
def add_to_cart(dish_name: str, quantity: int = 1) -> str:
    """
    将菜品添加到购物车
    如果购物车中已有该菜品，数量会累加
    Args:
        dish_name: 菜品名称
        quantity: 数量（默认为1）
    """
    return f'{{"ok": true, "cart_item": {{"name": "{dish_name}", "quantity": {quantity}, "unit_price": 0}}, "message": "已添加 {dish_name} x{quantity} 到购物车"}}'


@tool
def update_cart_quantity(dish_name: str, quantity: int) -> str:
    """
    修改购物车中菜品的数量
    Args:
        dish_name: 菜品名称
        quantity: 新的数量（设为0则移除）
    """
    return f'{{"ok": true, "update_name": "{dish_name}", "update_quantity": {quantity}, "message": "已将 {dish_name} 数量改为 {quantity}"}}'


@tool
def remove_from_cart(dish_name: str) -> str:
    """
    从购物车中移除指定菜品
    Args:
        dish_name: 菜品名称
    """
    return f'{{"ok": true, "remove_name": "{dish_name}", "message": "已将 {dish_name} 从购物车移除"}}'


@tool
def view_cart() -> str:
    """查看当前购物车内容"""
    return "请查看state中的cart信息。"


@tool
def clear_cart() -> str:
    """清空购物车"""
    return '{"ok": true, "message": "购物车已清空"}'
