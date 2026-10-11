"""Facilities agent: the shop space, its lease, and rent due dates."""

from backend.agents.base import AgentRole

FACILITIES = AgentRole(
    name="facilities",
    title="Facilities",
    description="Owns the shop space and lease: confirms rent amount, landlord, and due date, and drafts landlord replies. Sends rent payments to Accounting.",
    prompt_file="facilities.md",
    mcp_tools=frozenset({"get_lease", "list_leases", "get_cash_balance", "list_approvals", "draft_message"}),
)
