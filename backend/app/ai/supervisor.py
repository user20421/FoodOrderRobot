"""
Supervisor 调度中心（Tool Calling 版本）

职责：
  1. 接收用户输入
  2. 将请求交给 Tool Calling Agent 处理
  3. Agent 自主决策调用哪些工具来完成任务
  4. 确保返回格式统一

与旧版本的区别：
  - 旧版：Supervisor 自己做意图分类，硬编码路由到 5 个独立 Agent
  - 新版：单一大模型 Agent 通过 Tool Calling 自主选择工具，Supervisor 只做入口封装
"""
from app.ai.agent import run_agent_chat


async def run_chat(user_id: int, message: str, cart: list = None) -> dict:
    """
    对外接口：通过 Tool Calling Agent 执行一次对话
    返回 {"response": str, "cart": list}
    """
    return await run_agent_chat(user_id=user_id, message=message, cart=cart)
