from app.ai.agents.supervisor import get_supervisor_agent
from app.ai.agents.order_agent import order_agent
from app.ai.agents.inquiry_agent import inquiry_agent
from app.ai.agents.recommend_agent import recommend_agent
from app.ai.agents.service_agent import service_agent

AGENT_MAP = {
    "order": order_agent,
    "inquiry": inquiry_agent,
    "recommend": recommend_agent,
    "service": service_agent,
}

__all__ = ["get_supervisor_agent", "order_agent", "inquiry_agent", "recommend_agent", "service_agent", "AGENT_MAP"]
