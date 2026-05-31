"""
店铺信息相关工具
"""
from langchain_core.tools import tool


@tool
def get_store_info(query: str = None) -> str:
    """
    查询店铺信息，包括营业时间、地址、联系方式、配送政策等
    Args:
        query: 具体查询内容（如'营业时间'、'地址'、'配送'）
    """
    return f"查询店铺信息: {query or '全部'}"


@tool
def get_business_hours() -> str:
    """获取营业时间"""
    return "营业时间: 午餐11:00-14:30, 晚餐17:00-22:00"


@tool
def get_membership_info() -> str:
    """获取会员制度信息"""
    return "会员制度: 普通会员/银卡/金卡/钻石会员"
