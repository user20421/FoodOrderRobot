"""
问询智能体 (InquiryAgent)

职责：回答用户关于菜品、菜单、价格、库存、营业时间、配送等具体信息的询问。
"""
from app.ai.agents.base import BaseAgent
from app.ai.tools import (
    get_dish_detail,
    search_dishes_by_name,
    get_full_menu_text,
    get_system_info,
    check_stock,
    detect_info_intent,
    format_dish_detail,
    get_all_menu_items,
)


class InquiryAgent(BaseAgent):
    """
    问询智能体
    精确回答用户的信息查询，直接、准确、不啰嗦。
    """

    def __init__(self):
        super().__init__(
            name="问询专员",
            description="回答菜品信息、菜单、价格、库存、营业时间、配送等具体询问",
        )

    async def run(self, user_id: int, message: str, cart: list = None) -> dict:
        msg = message.lower()

        # 场景1：询问完整菜单
        if any(k in msg for k in ["菜单", "有什么菜", "菜名", "列表", "看看菜", "有哪些", "有什么吃的"]):
            menu_text = await get_full_menu_text()
            return {"response": menu_text}

        # 场景2：询问系统信息（营业时间、配送等）
        info_type = detect_info_intent(message)
        if info_type:
            info = get_system_info(info_type)
            return {"response": info}

        # 场景3：询问具体菜品（价格、辣度、库存等）
        all_items = await get_all_menu_items()
        matched_dish = None
        for it in all_items:
            if it.name in message:
                matched_dish = it
                break

        if matched_dish:
            detail = await get_dish_detail(matched_dish.name)

            # 判断用户具体问什么
            if any(k in msg for k in ["多少钱", "价格", "贵", "便宜", "价位"]):
                return {"response": f"{matched_dish.name} 的价格是 {matched_dish.price} 元。"}

            if any(k in msg for k in ["有", "吗", "有没有", "还有"]):
                stock = await check_stock(matched_dish.name)
                if stock > 0:
                    return {"response": f"有的！{matched_dish.name} 目前库存 {stock} 份，{matched_dish.price} 元。要不要来一份？"}
                else:
                    return {"response": f"抱歉，{matched_dish.name} 刚刚卖完了，您可以看看其他菜品。"}

            if any(k in msg for k in ["辣", "辣度", "辣不辣", "口味"]):
                spicy = "[辣]" * matched_dish.spicy_level if matched_dish.spicy_level else "[不辣]"
                return {"response": f"{matched_dish.name} 的辣度是 {spicy}，{matched_dish.description[:40]}..."}

            # 默认：返回菜品完整信息
            return {"response": format_dish_detail(detail)}

        # 场景4：按关键词搜索菜品
        keywords = self._extract_keywords(message)
        for kw in keywords:
            results = await search_dishes_by_name(kw)
            if results:
                lines = [f"找到以下与'{kw}'相关的菜品："]
                for it in results[:5]:
                    spicy = "[辣]" * it.spicy_level if it.spicy_level else "[不辣]"
                    lines.append(f"  {it.name} {spicy} {it.price}元")
                return {"response": "\n".join(lines)}

        # 兜底：返回菜单
        menu_text = await get_full_menu_text()
        return {"response": f"我没有找到您问的菜品，您可以看看我们的完整菜单：\n\n{menu_text}"}

    def _extract_keywords(self, message: str) -> list:
        """从消息中提取可能的搜索关键词"""
        stop_words = ["你们", "你们家", "有没有", "多少钱", "怎么样", "什么", "的", "了", "吗", "呢", "吧"]
        cleaned = message
        for sw in stop_words:
            cleaned = cleaned.replace(sw, " ")
        words = [w.strip() for w in cleaned.split() if 2 <= len(w.strip()) <= 6]
        seen = set()
        result = []
        for w in words:
            if w not in seen:
                seen.add(w)
                result.append(w)
        return result
