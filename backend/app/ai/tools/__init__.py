"""
AI 工具层
按领域拆分的工具函数，供各 Agent 调用
"""
from .parser_tools import extract_quantity, extract_preferences, extract_dish_names
from .menu_tools import (
    get_all_menu_items,
    search_dishes_by_name,
    get_dish_detail,
    search_by_preference,
    get_signature_dishes,
    check_stock,
    get_full_menu_text,
    get_menu_summary,
    format_dish_list,
    format_dish_detail,
)
from .order_tools import (
    get_user_orders,
    get_order_detail,
    get_latest_order,
    merge_cart,
    get_cart_summary,
    validate_cart_stock,
    submit_order,
    format_order_list,
    format_order_detail,
)
from .system_tools import get_system_info, detect_info_intent, STORE_INFO

__all__ = [
    # parser_tools
    "extract_quantity",
    "extract_preferences",
    "extract_dish_names",
    # menu_tools
    "get_all_menu_items",
    "search_dishes_by_name",
    "get_dish_detail",
    "search_by_preference",
    "get_signature_dishes",
    "check_stock",
    "get_full_menu_text",
    "get_menu_summary",
    "format_dish_list",
    "format_dish_detail",
    # order_tools
    "get_user_orders",
    "get_order_detail",
    "get_latest_order",
    "merge_cart",
    "get_cart_summary",
    "validate_cart_stock",
    "submit_order",
    "format_order_list",
    "format_order_detail",
    # system_tools
    "get_system_info",
    "detect_info_intent",
    "STORE_INFO",
]
