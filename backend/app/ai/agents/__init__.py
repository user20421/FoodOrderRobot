"""
多智能体模块
包含各个独立的业务领域 Agent 和共享基类
"""
from .base import BaseAgent
from .recommender import RecommenderAgent
from .inquiry import InquiryAgent
from .order import OrderAgent
from .order_tracking import OrderTrackingAgent
from .customer_service import CustomerServiceAgent

__all__ = [
    "BaseAgent",
    "RecommenderAgent",
    "InquiryAgent",
    "OrderAgent",
    "OrderTrackingAgent",
    "CustomerServiceAgent",
]
