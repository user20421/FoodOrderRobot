"""
工具导出
"""
from app.ai.tools.menu_tools import get_menu, search_dishes, get_dish_info, check_stock, get_recommended_dishes
from app.ai.tools.cart_tools import add_to_cart, update_cart_quantity, remove_from_cart, view_cart, clear_cart
from app.ai.tools.order_tools import confirm_order, get_my_orders, get_order_detail, cancel_order
from app.ai.tools.store_tools import get_store_info, get_business_hours, get_membership_info
from app.ai.tools.common_tools import rag_search, get_user_profile, greet_user

# 按领域分组的工具
MENU_TOOLS = [get_menu, search_dishes, get_dish_info, check_stock, get_recommended_dishes]
CART_TOOLS = [add_to_cart, update_cart_quantity, remove_from_cart, view_cart, clear_cart]
ORDER_TOOLS = [confirm_order, get_my_orders, get_order_detail, cancel_order]
STORE_TOOLS = [get_store_info, get_business_hours, get_membership_info]
COMMON_TOOLS = [rag_search, get_user_profile, greet_user]

# 所有工具
ALL_TOOLS = MENU_TOOLS + CART_TOOLS + ORDER_TOOLS + STORE_TOOLS + COMMON_TOOLS
