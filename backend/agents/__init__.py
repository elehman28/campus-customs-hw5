"""The Campus Customs agent team. Any agent may delegate to any other (full mesh)."""

from backend.agents.accounting import ACCOUNTING
from backend.agents.base import AgentRole, get_agent, run_agent
from backend.agents.boss import BOSS
from backend.agents.customer_service import CUSTOMER_SERVICE
from backend.agents.facilities import FACILITIES
from backend.agents.inventory import INVENTORY

ROLES: dict[str, AgentRole] = {
    r.name: r for r in (BOSS, INVENTORY, ACCOUNTING, FACILITIES, CUSTOMER_SERVICE)
}

__all__ = ["ROLES", "AgentRole", "get_agent", "run_agent"]
