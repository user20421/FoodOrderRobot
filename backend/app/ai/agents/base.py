"""
Agent 基类
所有业务 Agent 继承此类，实现统一的 run 接口
"""
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """
    AI Agent 基类

    每个 Agent 代表一个独立的业务领域智能体：
    - 拥有明确的职责边界
    - 拥有专属的工具集
    - 通过 run() 方法对外提供服务
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def run(self, user_id: int, message: str, cart: list = None) -> dict:
        """
        执行 Agent 的核心逻辑

        Args:
            user_id: 用户ID
            message: 用户输入消息
            cart: 当前购物车状态

        Returns:
            dict: 必须包含 "response" 键，可选包含 "cart" 键
            例如：{"response": "回复内容", "cart": [...]}
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name}>"
