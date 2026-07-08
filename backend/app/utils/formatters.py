"""
文本格式化工具
"""


def order_status_text(status: str) -> str:
    """订单状态转中文"""
    mapping = {
        "pending": "待确认",
        "confirmed": "已确认",
        "completed": "已完成",
        "cancelled": "已取消",
    }
    return mapping.get(status, status)
