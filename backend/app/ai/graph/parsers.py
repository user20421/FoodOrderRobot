"""
意图与日期解析工具
从用户消息中提取日期、订单查询意图等结构化信息。
"""
import re
import json
from datetime import date, timedelta
from typing import Optional

from app.ai.llm import get_llm
from app.core.logging_config import get_logger
from langchain_core.messages import SystemMessage, HumanMessage

logger = get_logger(__name__)


def parse_date_from_message(msg: str) -> Optional[date]:
    """从用户消息中解析日期，支持今天/昨天/前天/X月X日/YYYY-MM-DD等"""
    msg = msg.strip()
    today = date.today()

    # 相对日期
    if "前天" in msg:
        return today - timedelta(days=2)
    if "昨天" in msg:
        return today - timedelta(days=1)
    if "今天" in msg:
        return today

    # 2026年5月31日 / 2026-05-31 / 2026/05/31
    m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', msg)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 5月31日 / 5月31号
    m = re.search(r'(\d{1,2})月(\d{1,2})[日号]', msg)
    if m:
        return date(today.year, int(m.group(1)), int(m.group(2)))

    # 5/31 / 5-31
    m = re.search(r'(\d{1,2})[-/](\d{1,2})', msg)
    if m:
        return date(today.year, int(m.group(1)), int(m.group(2)))

    return None


async def parse_order_intent(user_message: str) -> dict:
    """
    用 LLM 解析用户的订单查询意图，返回结构化参数。
    LLM 只负责理解语言，不接触真实订单数据，彻底避免编造。
    """
    current_year = date.today().year
    system_prompt = (
        "你是订单查询意图解析器。请严格只输出JSON，不要输出任何其他文字、解释或示例。\n"
        f"当前年份是 {current_year} 年，解析日期时请使用 {current_year} 年。\n\n"
        '输出格式（严格按此格式，不要加任何额外内容）：\n'
        '{"limit": 数字, "date": "YYYY-MM-DD" 或 null, "sort": "desc" 或 "asc", "single": true 或 false}\n\n'
        "解析规则：\n"
        '1. limit：用户要查多少条。默认10，最大50。"最近一条"→1，"最近两条"→2，"所有"→50。\n'
        '2. date：如果用户指定了具体日期（如"今天的""昨天的""5月31日的"），填YYYY-MM-DD；否则null。\n'
        '3. sort："desc"=最新在前（默认），"asc"=最旧在前。用户说"最早"时填"asc"，说"最近/最新"时填"desc"。\n'
        '4. single：用户是否只要求"一条/一个/单笔"订单。true 时 limit 强制为1。\n\n'
        "示例（仅供理解，不要输出）：\n"
        '- "查询我的订单" → {"limit": 10, "date": null, "sort": "desc", "single": false}\n'
        '- "最近的一次订单" → {"limit": 1, "date": null, "sort": "desc", "single": true}\n'
        '- "最早的两条订单" → {"limit": 2, "date": null, "sort": "asc", "single": false}'
    )

    try:
        llm = get_llm(temperature=0.0)
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f'用户消息："{user_message}"\n\n请只输出JSON：'),
        ])
        content = response.content.strip().replace("```json", "").replace("```", "").strip()
        # 提取第一个 { 到最后一个 } 之间的内容，防止LLM输出额外文字
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content = content[start:end+1]
        result = json.loads(content)
        # 参数校验
        result["limit"] = max(1, min(int(result.get("limit", 10)), 50))
        result["sort"] = "asc" if result.get("sort") == "asc" else "desc"
        result["single"] = bool(result.get("single", False))
        if result["single"]:
            result["limit"] = 1
        # 正则兜底：总是用正则重新解析日期，覆盖 LLM 可能错误的日期
        parsed = parse_date_from_message(user_message)
        if parsed:
            result["date"] = parsed.isoformat()
        return result
    except Exception as e:
        logger.warning(f"[OrderIntent] LLM 解析失败，使用默认参数: {e}")
        # 兜底：尝试正则解析日期
        parsed = parse_date_from_message(user_message)
        return {
            "limit": 10,
            "date": parsed.isoformat() if parsed else None,
            "sort": "desc",
            "single": False,
        }
