"""
Supervisor 智能体
负责意图识别和路由决策
"""
import json
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.ai.llm import get_llm
from app.ai.prompts.templates import SUPERVISOR_SYSTEM_PROMPT
from app.core.logging_config import get_logger

logger = get_logger(__name__)

INTENT_TO_AGENT = {
    "order": "order",
    "inquiry": "inquiry",
    "recommend": "recommend",
    "service": "service",
}

# DashScope SDK bug: API报错时 KeyError('request')
DASHSCOPE_KEYERROR_MSG = "调用大模型服务失败，可能是 API Key 无效、模型不可用或额度已用完。"


class SupervisorAgent:
    """主管智能体"""

    def __init__(self):
        self.llm = get_llm(temperature=0.1)

    async def classify_intent(self, message: str, history: list = None) -> Dict[str, Any]:
        """
        分析用户意图，返回路由决策
        LLM失败时回退到关键词匹配，保证系统可用性
        """
        try:
            messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)]

            # 添加历史上下文
            if history:
                for h in history[-4:]:
                    role = h.get("role", "")
                    content = h.get("content", "")
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        messages.append(AIMessage(content=content))

            messages.append(HumanMessage(content=f"用户消息：{message}\n\n请判断意图并输出JSON。"))

            response = await self.llm.ainvoke(messages)
            content = response.content.strip()

            # 解析JSON
            content = content.replace("```json", "").replace("```", "").strip()
            result = json.loads(content)

            intent = result.get("intent", "service")
            # 确保intent有效
            if intent not in INTENT_TO_AGENT:
                intent = "service"

            return {
                "intent": intent,
                "reason": result.get("reason", ""),
                "agent": INTENT_TO_AGENT.get(intent, "service"),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"[Supervisor] JSON解析失败: {e}, content={content[:100]}")
            return self._fallback_intent_detection(message)
        except KeyError as e:
            # DashScope SDK bug: API错误时 KeyError('request')
            if str(e) == "'request'":
                logger.warning(f"[Supervisor] {DASHSCOPE_KEYERROR_MSG}")
            else:
                logger.warning(f"[Supervisor] KeyError: {e}")
            return self._fallback_intent_detection(message)
        except Exception as e:
            logger.error(f"[Supervisor] 意图识别失败: {e}")
            return self._fallback_intent_detection(message)

    def _fallback_intent_detection(self, message: str) -> Dict[str, Any]:
        """关键词回退检测"""
        msg = message.lower()

        order_keywords = ["来一份", "来一个", "来碗", "来盘", "加一份", "加一份", "点一份", "点一个", "我要点", "给我点", "添加", "购物车", "下单", "买单", "结账", "不要了", "删掉", "删除", "改为", "清空购物车", "确认下单"]
        inquiry_keywords = ["多少钱", "价格", "有什么", "菜单", "辣不辣", "口味", "介绍", "是什么", "有哪些", "有什么菜", "查看菜单", "菜单一览", "有什么吃的"]
        recommend_keywords = ["推荐", "什么好吃", "招牌", "特色", "不知道吃", "建议", "推荐菜", "给我推荐"]
        service_keywords = ["查询订单", "查看订单", "所有订单", "我的订单", "订单记录", "订单状态", "订单详情"]

        for kw in order_keywords:
            if kw in msg:
                return {"intent": "order", "reason": f"关键词匹配: {kw}", "agent": "order"}

        for kw in recommend_keywords:
            if kw in msg:
                return {"intent": "recommend", "reason": f"关键词匹配: {kw}", "agent": "recommend"}

        for kw in inquiry_keywords:
            if kw in msg:
                return {"intent": "inquiry", "reason": f"关键词匹配: {kw}", "agent": "inquiry"}

        for kw in service_keywords:
            if kw in msg:
                return {"intent": "service", "reason": f"关键词匹配: {kw}", "agent": "service"}

        return {"intent": "service", "reason": "未匹配到明确意图", "agent": "service"}


_supervisor_agent = None

def get_supervisor_agent() -> SupervisorAgent:
    """获取 SupervisorAgent 单例（懒加载）"""
    global _supervisor_agent
    if _supervisor_agent is None:
        _supervisor_agent = SupervisorAgent()
    return _supervisor_agent
