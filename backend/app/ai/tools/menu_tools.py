"""
菜单工具
提供菜单查询、搜索、筛选、格式化等能力
"""
from app.core.database import AsyncSessionLocal
from app.services.menu_service import get_menu


# 招牌菜清单（可作为数据库字段扩展）
SIGNATURE_DISHES = ["宫保鸡丁", "麻婆豆腐", "红烧肉", "水煮牛肉", "酸菜鱼", "糖醋里脊", "清蒸鲈鱼"]

# 分类排序
CATEGORY_ORDER = ["热菜", "素菜", "海鲜", "凉菜", "汤品", "主食"]


async def get_all_menu_items() -> list:
    """获取全部菜单项"""
    async with AsyncSessionLocal() as db:
        return await get_menu(db)


async def search_dishes_by_name(keyword: str) -> list:
    """按关键词搜索菜品"""
    items = await get_all_menu_items()
    keyword = keyword.lower()
    return [it for it in items if keyword in it.name.lower()]


async def get_dish_detail(dish_name: str) -> dict | None:
    """
    获取指定菜品的详细信息。

    返回：{"name", "price", "spicy_level", "category", "description", "stock", "available"}
    或 None（菜品不存在）
    """
    items = await get_all_menu_items()
    for it in items:
        if it.name == dish_name:
            return {
                "name": it.name,
                "price": it.price,
                "spicy_level": it.spicy_level,
                "category": it.category or "其他",
                "description": it.description or "",
                "stock": it.stock,
                "available": it.stock > 0,
            }
    return None


async def search_by_preference(
    spicy_level: int = None,
    categories: list = None,
    tags: list = None,
    dietary: list = None,
    max_price: float = None,
    limit: int = 6,
) -> list:
    """
    按用户偏好筛选菜品。

    Args:
        spicy_level: 辣度等级（0-5），None 表示不限制
        categories: 分类列表，如 ["热菜", "素菜"]
        tags: 标签列表，如 ["招牌", "下饭"]
        dietary: 饮食限制，如 ["no_spicy", "vegetarian"]
        max_price: 最高价格
        limit: 返回数量上限

    Returns:
        符合条件的菜品列表（字典格式）
    """
    items = await get_all_menu_items()
    if not items:
        return []

    filtered = items

    # 按辣度筛选
    if spicy_level is not None:
        if "no_spicy" in (dietary or []):
            filtered = [it for it in filtered if it.spicy_level == 0]
        else:
            filtered = [it for it in filtered if it.spicy_level >= spicy_level]

    # 按分类筛选
    if categories:
        filtered = [it for it in filtered if (it.category or "其他") in categories]

    # 按饮食限制筛选
    if dietary:
        if "vegetarian" in dietary:
            filtered = [
                it for it in filtered
                if it.category == "素菜" or not any(m in it.name for m in ["肉", "鸡", "猪", "牛", "鱼", "虾", "蟹"])
            ]

    # 按价格筛选
    if max_price is not None:
        filtered = [it for it in filtered if it.price <= max_price]

    # 按标签排序/筛选
    if tags:
        # 招牌标签：优先招牌菜
        if "招牌" in tags:
            sig = [it for it in filtered if it.name in SIGNATURE_DISHES]
            if len(sig) < 3:
                sig = [it for it in filtered if it.category == "热菜"][:5]
            filtered = sig
        # 下饭标签：优先辣味菜和经典菜
        elif "下饭" in tags:
            filtered = [
                it for it in filtered
                if it.spicy_level >= 2 or any(m in it.name for m in ["酸菜", "鱼香", "宫保", "麻婆", "糖醋", "回锅"])
            ]
        # 儿童标签：优先不辣的家常菜
        elif "儿童" in tags:
            filtered = [it for it in filtered if it.spicy_level == 0 and (it.category in ["热菜", "素菜", "汤品", "主食"])]

    # 默认：热菜优先
    if not tags and not categories:
        filtered = [it for it in filtered if it.category == "热菜"][:limit]

    return filtered[:limit]


async def get_signature_dishes(limit: int = 5) -> list:
    """获取招牌/热门菜品"""
    items = await get_all_menu_items()
    sig = [it for it in items if it.name in SIGNATURE_DISHES]
    if len(sig) < 3:
        sig = [it for it in items if it.category == "热菜"][:limit]
    return sig[:limit]


async def check_stock(dish_name: str) -> int:
    """查询某菜品的库存"""
    detail = await get_dish_detail(dish_name)
    return detail["stock"] if detail else 0


async def get_full_menu_text() -> str:
    """获取格式化的完整菜单文本（Markdown 表格格式）"""
    items = await get_all_menu_items()
    if not items:
        return "本店菜单正在更新中，请稍后再来～"

    groups = {}
    for it in items:
        groups.setdefault(it.category or "其他", []).append(it)

    lines = ["**本店菜单一览**"]
    for category in sorted(groups.keys(), key=lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99):
        lines.append(f"\n**【{category}】**")
        lines.append("")
        lines.append("| 菜品 | 辣度 | 价格 | 状态 |")
        lines.append("|------|------|------|------|")
        for it in groups[category]:
            spicy = "[辣]" * it.spicy_level if it.spicy_level else "[不辣]"
            if it.stock == 0:
                status = "已售罄"
            elif it.stock < 20:
                status = f"库存紧张({it.stock})"
            else:
                status = "有货"
            lines.append(f"| {it.name} | {spicy} | {it.price}元 | {status} |")
        lines.append("")

    lines.append("看上哪道直接告诉我，我来帮您下单～")
    return "\n".join(lines)


async def get_menu_summary() -> str:
    """获取菜单摘要（用于注入 LLM 上下文）"""
    items = await get_all_menu_items()
    if not items:
        return ""
    cats = {}
    for it in items:
        cats.setdefault(it.category or "其他", []).append(f"{it.name}({it.price}元)")
    return "\n".join([f"{cat}：{', '.join(names[:8])}" for cat, names in cats.items()])


def format_dish_list(dishes: list, title: str = "推荐菜品") -> str:
    """将菜品列表格式化为 Markdown 表格推荐文案"""
    if not dishes:
        return "本店暂时没有完全符合您要求的菜品，您可以看看菜单或直接告诉我菜名哦～"

    lines = [f"**>> {title}**", ""]
    lines.append("| 菜品 | 辣度 | 价格 | 简介 |")
    lines.append("|------|------|------|------|")
    for it in dishes:
        spicy = "[辣]" * it.spicy_level if it.spicy_level else "[不辣]"
        desc = it.description[:30] if it.description else ""
        stock_warn = "库存紧张" if it.stock < 20 else ""
        status = stock_warn if stock_warn else ""
        lines.append(f"| {it.name} | {spicy} | {it.price}元 | {desc}{status} |")

    lines.append("")
    lines.append("看上哪道直接告诉我，比如：来一份宫保鸡丁！")
    return "\n".join(lines)


def format_dish_detail(detail: dict) -> str:
    """将菜品详情格式化为口语化描述"""
    if not detail:
        return "抱歉，本店暂时没有这道菜。"

    spicy = "[辣]" * detail["spicy_level"] if detail["spicy_level"] else "[不辣]"
    stock_text = "有货" if detail["available"] else "已售罄"

    lines = [
        f"{detail['name']} {spicy} {detail['price']}元",
        f"分类：{detail['category']}",
        f"介绍：{detail['description'][:60]}..." if detail["description"] else "",
        f"库存状态：{stock_text}（{detail['stock']}份）",
    ]
    return "\n".join(filter(None, lines))
