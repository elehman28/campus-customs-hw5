"""Accounting agent: cash, vendor invoices, discount math, and payment
approval requests. The only role that can ask a human to approve a payment."""

from backend.agents.base import AgentRole

ACCOUNTING = AgentRole(
    name="accounting",
    title="Accounting",
    description="Owns cash and bills: checks the balance, invoices, and payments, prices discounts against cost, and files payment requests for human approval.",
    prompt_file="accounting.md",
    mcp_tools=frozenset({
        "get_cash_balance", "list_invoices", "list_payments", "get_pricing", "quote_bulk_price",
        "check_vendor_can_ship", "get_lease", "request_payment_approval", "list_approvals",
    }),
)
