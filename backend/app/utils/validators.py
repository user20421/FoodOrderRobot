"""
输入验证工具
"""
import re


def validate_phone(phone: str) -> bool:
    """验证手机号"""
    if not phone:
        return True
    return bool(re.match(r"^1[3-9]\d{9}$", phone))


def validate_username(username: str) -> bool:
    """验证用户名"""
    return bool(re.match(r"^[a-zA-Z0-9_\u4e00-\u9fa5]{3,50}$", username))


def extract_quantity(text: str) -> int:
    """从文本中提取数量（支持中文数字）"""
    chinese_nums = {
        '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    }

    # 先找阿拉伯数字
    match = re.search(r'(\d+)', text)
    if match:
        return int(match.group(1))

    # 再找中文数字
    for cn, num in chinese_nums.items():
        if cn in text:
            return num

    return 1  # 默认1份
