"""Boss agent: reads the board, decides who owns each ticket, delegates, and
checks the work before reporting back to the human."""

from backend.agents.base import AgentRole

BOSS = AgentRole(
    name="boss",
    title="Boss",
    description="Runs the board: triages tickets, assigns work to the right teammates, checks results, and reports to the human.",
    prompt_file="boss.md",
    mcp_tools=frozenset({"get_cash_balance", "list_approvals", "list_drafts"}),
)
