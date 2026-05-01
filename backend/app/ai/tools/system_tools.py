"""
系统信息工具
提供店铺营业时间、配送、联系方式等静态信息
"""

# 店铺信息配置（可扩展为从数据库或配置文件读取）
STORE_INFO = {
    "name": "智能点餐餐厅",
    "business_hours": "每天 10:00-22:00",
    "delivery": {
        "available": True,
        "free_range_km": 3,
        "fee_description": "3公里内免配送费，超出范围按距离收取少量配送费",
    },
    "address": "具体地址请查看店内公告",
    "contact": "前台电话请咨询店内工作人员",
    "payment_methods": ["微信支付", "支付宝", "现金"],
    "service_types": ["堂食", "外卖配送", "到店自取"],
}


def get_system_info(info_type: str = None) -> str:
    """
    获取系统/店铺信息。

    Args:
        info_type: 信息类型，可选：business_hours, delivery, address, contact, payment, service
                  为 None 时返回完整信息

    Returns:
        格式化的信息字符串
    """
    if info_type == "business_hours" or info_type == "营业时间" or info_type == "时间":
        return f"本店营业时间为 {STORE_INFO['business_hours']}。"

    if info_type == "delivery" or info_type == "配送" or info_type == "外卖":
        d = STORE_INFO["delivery"]
        return (
            f"本店{'支持' if d['available'] else '暂不支持'}外卖配送。"
            f"{d['fee_description']}。"
        )

    if info_type == "address" or info_type == "地址" or info_type == "在哪":
        return f"本店{STORE_INFO['address']}。"

    if info_type == "contact" or info_type == "电话" or info_type == "联系方式":
        return f"{STORE_INFO['contact']}。"

    if info_type == "payment" or info_type == "支付":
        return f"本店支持支付方式：{', '.join(STORE_INFO['payment_methods'])}。"

    if info_type == "service" or info_type == "服务":
        return f"本店提供服务：{', '.join(STORE_INFO['service_types'])}。"

    # 返回完整信息
    lines = [
        f"【{STORE_INFO['name']}】",
        f"营业时间：{STORE_INFO['business_hours']}",
        f"配送服务：{STORE_INFO['delivery']['fee_description']}",
        f"地址：{STORE_INFO['address']}",
        f"联系方式：{STORE_INFO['contact']}",
        f"支付方式：{', '.join(STORE_INFO['payment_methods'])}",
        f"服务类型：{', '.join(STORE_INFO['service_types'])}",
    ]
    return "\n".join(lines)


def detect_info_intent(message: str) -> str | None:
    """
    检测用户消息是否在询问系统信息。

    返回：info_type 或 None
    """
    msg = message.lower()
    keywords_map = {
        "business_hours": ["营业", "时间", "几点", "开门", "关门"],
        "delivery": ["配送", "外卖", "送到", "打包", "带走"],
        "address": ["地址", "在哪", "位置", "怎么去"],
        "contact": ["电话", "联系", "怎么找", "客服"],
        "payment": ["支付", "付款", "微信", "支付宝", "现金"],
        "service": ["堂食", "自取", "服务"],
    }
    for info_type, keywords in keywords_map.items():
        if any(k in msg for k in keywords):
            return info_type
    return None
