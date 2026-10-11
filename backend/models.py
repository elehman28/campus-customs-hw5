"""Data types shared by the Campus Customs agent team."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = (
    "boss", "inventory", "accounting", "facilities", "customer_service",
)

TicketOutcome = Literal["resolved", "waiting_approval", "blocked", "in_progress", "needs_human"]


@dataclass
class TeamDeps:
    """Run context passed to every agent (and on to anyone it delegates to)."""

    team_run_id: str             # one id for the whole team run (Boss + every delegate)
    agent_run_id: str            # this agent's own loop
    agent: AgentName
    depth: int = 0               # 0 = Boss started by a human; +1 per delegation
    chain: list[AgentName] = field(default_factory=list)  # who delegated to whom, root first
    ticket_id: int | None = None


class AgentReport(BaseModel):
    """What every agent returns when its loop ends (to a human or to the agent that delegated)."""

    agent: AgentName
    ticket_ids: list[int] = Field(default_factory=list, description="Tickets this report covers.")
    outcome: TicketOutcome = Field(description="Where the work stands when this agent stops.")
    summary: str = Field(description="2-4 sentences: what was found and done, with real numbers from the tools.")
    facts_used: list[str] = Field(
        default_factory=list,
        description="Key facts this report relies on, each with the MCP tool it came from, e.g. 'CC-TEE-WHITE S qty=0 (check_stock)'.",
    )
    actions_taken: list[str] = Field(default_factory=list, description="Writes made through MCP tools (status changes, drafts, approval requests).")
    approval_ids: list[int] = Field(default_factory=list, description="Payment approval requests filed, waiting for a human.")
    draft_ids: list[int] = Field(default_factory=list, description="Draft messages saved on the board (never sent).")
    delegated_to: list[AgentName] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list, description="What is stopping the ticket from being resolved.")
    next_steps: list[str] = Field(default_factory=list, description="What a human or another agent must do next.")


class DelegationResult(BaseModel):
    """Returned by the delegate_task tool to the agent that asked for help."""

    to_agent: AgentName
    ok: bool
    report: AgentReport | None = None
    error: str | None = None


class TeamRunRequest(BaseModel):
    """Start a team run: one ticket, or the whole open board if ticket_id is None."""

    ticket_id: int | None = None
    instructions: str = ""


class TeamRunResult(BaseModel):
    team_run_id: str
    ok: bool
    report: AgentReport | None = None
    error: str | None = None
    model_requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
