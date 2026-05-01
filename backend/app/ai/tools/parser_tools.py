"""
解析工具
负责从用户自然语言消息中提取结构化信息
"""
import re


CN_NUMBERS = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
    "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
}


def extract_quantity(message: str, dish_name: str) -> int:
    """
    从用户消息中提取某道菜的数量。

    支持的格式：
      - 菜名后接数字：宫保鸡丁x2、宫保鸡丁×2、宫保鸡丁*2
      - 菜名前接数字：2份宫保鸡丁、来2份宫保鸡丁、两份宫保鸡丁
      - 默认：无显式数量则返回 1
    """
    # 格式1：菜名后接乘号+数字
    m = re.search(re.escape(dish_name) + r"[\s]*[×xX*]\s*(\d+)", message)
    if m:
        return int(m.group(1))

    # 格式2：数字+量词+菜名
    m = re.search(r"(\d+)\s*(?:份|个|碗|盘|斤|例)\s*" + re.escape(dish_name), message)
    if m:
        return int(m.group(1))

    # 格式3：中文数字+量词+菜名
    for cn, num in CN_NUMBERS.items():
        if re.search(cn + r"(?:份|个|碗|盘|斤|例)\s*" + re.escape(dish_name), message):
            return num

    return 1


def extract_preferences(message: str) -> dict:
    """
    从用户消息中提取饮食偏好关键词。

    返回：{"spicy_level": int|None, "categories": list, "tags": list, "dietary": list}
    """
    msg = message.lower()
    prefs = {
        "spicy_level": None,
        "categories": [],
        "tags": [],
        "dietary": [],
    }

    # 辣度
    if any(k in msg for k in ["很辣", "特辣", "麻辣", "重辣"]):
        prefs["spicy_level"] = 4
    elif any(k in msg for k in ["辣", "微辣", "中辣"]):
        prefs["spicy_level"] = 3
    elif any(k in msg for k in ["不辣", "清淡", "微辣"]):
        prefs["spicy_level"] = 0

    # 分类
    CATEGORY_KEYWORDS = {
        "素菜": ["素菜", "素食", "蔬菜"],
        "荤菜": ["荤菜", "肉菜"],
        "海鲜": ["海鲜", "鱼", "虾", "贝", "蟹"],
        "汤品": ["汤", "粥"],
        "主食": ["主食", "饭", "炒饭", "面", "粥"],
        "凉菜": ["凉菜", "冷菜"],
        "热菜": ["热菜"],
    }
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in msg for k in keywords):
            prefs["categories"].append(cat)

    # 饮食标签
    TAG_KEYWORDS = {
        "招牌": ["招牌", "特色", "热门", "经典", "好吃", "推荐"],
        "下饭": ["下饭", "开胃", "配饭"],
        "清淡": ["清淡", "健康", "低脂", "减脂"],
        "儿童": ["小孩", "儿童", "老人", "温和"],
    }
    for tag, keywords in TAG_KEYWORDS.items():
        if any(k in msg for k in keywords):
            prefs["tags"].append(tag)

    # 饮食限制
    if any(k in msg for k in ["不吃辣", "忌辣", "过敏"]):
        prefs["dietary"].append("no_spicy")
    if any(k in msg for k in ["素食", "不吃肉", "斋"]):
        prefs["dietary"].append("vegetarian")

    return prefs


def extract_dish_names(message: str, menu_items: list) -> list:
    """
    从消息中提取所有在菜单中出现的菜品名及其数量。

    返回：[{"name": str, "menu_item_id": int, "quantity": int, "unit_price": float}, ...]
    """
    found = []
    for item in menu_items:
        if item.name in message:
            qty = extract_quantity(message, item.name)
            if qty > 0:
                found.append({
                    "name": item.name,
                    "menu_item_id": item.id,
                    "quantity": qty,
                    "unit_price": item.price,
                })
    return found
