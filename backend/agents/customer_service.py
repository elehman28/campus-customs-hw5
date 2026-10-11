"""Customer Service agent: the customer's point of contact. Drafts every
customer reply (never sends) using facts from teammates and MCP tools."""

from backend.agents.base import AgentRole

CUSTOMER_SERVICE = AgentRole(
    name="customer_service",
    title="Customer Service",
    description="Talks to customers: checks what can be promised (stock, price, timing) and drafts customer replies on the board. Never sends anything.",
    prompt_file="customer_service.md",
    mcp_tools=frozenset({"check_stock", "get_pricing", "quote_bulk_price", "draft_message", "list_drafts"}),
)
