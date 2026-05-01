"""
Supervisor 调度中心
多智能体架构的核心路由器

职责：
  1. 接收用户输入
  2. 判断用户意图（LLM 智能分类 + 关键词 Fallback）
  3. 将请求分发给最合适的业务 Agent
  4. 确保返回格式统一

不处理任何业务逻辑，只做路由。
"""
import os

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.agents import (
    RecommenderAgent,
    InquiryAgent,
    OrderAgent,
    OrderTrackingAgent,
    CustomerServiceAgent,
)
from app.ai.tools import get_all_menu_items, detect_info_intent
from app.core.config import settings


def _get_llm():
    """获取 LLM 实例（DashScope）"""
    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未设置")
    return ChatTongyi(
        model=settings.chat_model,
        dashscope_api_key=api_key,
        temperature=0.1,
    )


class Supervisor:
    """
    智能调度中心

    管理多个业务 Agent，根据用户消息判断最合适的 Agent 来处理。
    支持 LLM 智能调度 和 关键词 Fallback 两种模式。
    """

    # 意图到 Agent 的映射
    AGENT_MAP = {
        "recommend": RecommenderAgent,
        "inquiry": InquiryAgent,
        "order": OrderAgent,
        "order_tracking": OrderTrackingAgent,
        "customer_service": CustomerServiceAgent,
    }

    def __init__(self):
        # 延迟实例化：按需创建 Agent 实例
        self._agent_instances = {}

    def _get_agent(self, intent: str):
        """获取或创建指定意图的 Agent 实例"""
        if intent not in self._agent_instances:
            agent_cls = self.AGENT_MAP.get(intent)
            if agent_cls:
                self._agent_instances[intent] = agent_cls()
        return self._agent_instances.get(intent)

    async def classify_intent(self, message: str) -> str:
        """
        判断用户意图，返回 Agent 名称

        分类优先级（从高到低）：
        1. 前置规则：系统信息查询 → inquiry
        2. 前置规则：具体菜品+询问语气 → inquiry
        3. LLM 分类（有 API Key 时）
        4. 关键词 Fallback（无 API Key 时）
        """
        msg = message.lower()

        # ===== 前置规则1：系统信息查询 =====
        if detect_info_intent(message):
            return "inquiry"

        # ===== 前置规则2：具体菜品 + 询问语气 → inquiry（不是点餐） =====
        # 例如 "有宫保鸡丁吗"、"宫保鸡丁多少钱"、"宫保鸡丁辣不辣"
        items = await get_all_menu_items()
        for it in items:
            if it.name in message:
                if any(k in msg for k in ["多少钱", "价格", "贵", "便宜", "价位", "有", "吗", "怎么样", "好吃", "有没有", "是什么", "介绍", "辣不辣", "辣度", "口味", "库存"]):
                    return "inquiry"

        # ===== LLM 智能分类 =====
        try:
            llm = _get_llm()
            system_msg = (
                "你是一个意图分类助手。请根据用户输入，判断其意图类别，只输出一个单词，不要解释。\n"
                "可选类别：\n"
                "- recommend: 用户想要推荐菜品，或问'有什么好吃的/辣的/清淡的/素菜/海鲜/汤/主食/招牌/下饭'等\n"
                "- inquiry: 用户想查询具体信息（菜品价格、菜单、库存、营业时间、配送等）\n"
                "- order: 用户想点餐/下单/加购/来一份某菜/确认下单/查看购物车\n"
                "- order_tracking: 用户想查询自己的订单历史/订单状态/我点了什么\n"
                "- customer_service: 其他闲聊、问候、感谢、告别或无法分类\n"
                "只输出类别名。"
            )
            result = await llm.ainvoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=message),
            ])
            intent = result.content.strip().lower()
        except Exception:
            # LLM 不可用，fallback 到关键词匹配
            intent = self._keyword_classify(msg)

        # 归一化：确保返回有效的意图标签
        intent = self._normalize_intent(intent)
        return intent

    def _keyword_classify(self, msg: str) -> str:
        """关键词意图匹配（无 LLM 时使用）"""

        # 订单追踪
        if any(k in msg for k in ["订单", "我点了", "查订单", "我的单", "历史", "消费记录"]):
            # 但要排除"来一份..."这种点餐表达中包含"单"字的情况
            if not any(k in msg for k in ["来一份", "来份", "要一份", "点"]):
                return "order_tracking"

        # 点餐
        if any(k in msg for k in ["来一份", "来份", "要一份", "点", "加", "确认", "下单", "买单", "结账", "就这些", "购物车"]):
            # 排除"推荐几个菜"中的"菜"
            if "推荐" not in msg:
                return "order"

        # 推荐
        if any(k in msg for k in [
            "推荐", "好吃", "招牌", "特色", "热门", "经典",
            "辣", "不辣", "清淡", "低脂", "好吃", "哪个",
            "素菜", "荤菜", "肉", "海鲜", "鱼", "虾",
            "汤", "粥", "主食", "下饭", "开胃", "小孩", "儿童", "老人"
        ]):
            return "recommend"

        # 问询（菜单相关）
        if any(k in msg for k in ["菜单", "有什么菜", "菜名", "列表", "看看菜", "有哪些", "有什么吃的"]):
            return "inquiry"

        # 客服（问候/感谢/告别）
        if any(k in msg for k in ["你好", "在吗", "hi", "hello", "您好", "谢谢", "感谢", "再见", "拜拜", "bye"]):
            return "customer_service"

        # 默认兜底
        return "customer_service"

    def _normalize_intent(self, intent: str) -> str:
        """将 LLM 输出归一化为标准意图标签"""
        valid = {"recommend", "inquiry", "order", "order_tracking", "customer_service"}
        if intent in valid:
            return intent
        # 部分匹配
        for v in valid:
            if v in intent:
                return v
        # 映射常见别名
        aliases = {
            "menu": "inquiry",
            "query": "inquiry",
            "chat": "customer_service",
            "greeting": "customer_service",
            "farewell": "customer_service",
        }
        return aliases.get(intent, "customer_service")

    async def run(self, user_id: int, message: str, cart: list = None) -> dict:
        """
        Supervisor 主入口
        1. 判断意图
        2. 调用对应 Agent
        3. 返回统一格式结果
        """
        intent = await self.classify_intent(message)
        agent = self._get_agent(intent)

        if not agent:
            # 理论上不会发生，但做兜底
            agent = CustomerServiceAgent()

        result = await agent.run(user_id, message, cart)

        # 确保返回格式统一
        if "cart" not in result:
            result["cart"] = cart or []
        return result


# 全局 Supervisor 实例（单例）
_supervisor = Supervisor()


async def run_chat(user_id: int, message: str, cart: list = None) -> dict:
    """
    对外接口：通过 Supervisor 调度执行一次对话
    返回 {"response": str, "cart": list}
    """
    try:
        result = await _supervisor.run(user_id, message, cart)
    except Exception as e:
        return {
            "response": f"服务暂时异常，请稍后重试。错误信息：{str(e)[:200]}",
            "cart": cart or [],
        }
    if "cart" not in result:
        result["cart"] = cart or []
    return result
