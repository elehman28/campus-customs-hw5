"""Shared machinery for all five agents.

- AgentRole:      what makes each role different (prompt file, MCP tools, description)
- build_agent():  one pydantic-ai Agent per role: gpt-6-luna, its prompt, its MCP
                  tool view, and the delegate_task tool
- run_agent():    the agent loop. Steps through agent.iter() node by node and
                  appends every step to output/audit_trail.json
- delegate_task:  full connectivity. Any agent can hand work to any other agent,
                  guarded by a depth limit and a no-cycles rule so a run can't
                  ping-pong forever
"""

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    ModelRequest, ModelResponse, RetryPromptPart, SystemPromptPart, TextPart,
    ThinkingPart, ToolCallPart, ToolReturnPart, UserPromptPart,
)
from pydantic_ai.usage import RunUsage

from backend import audit
from backend.config import (
    AGENT_RETRIES, MAX_DELEGATION_DEPTH, MODEL_NAME, MODEL_SETTINGS, PROMPTS_DIR,
    TEAM_USAGE_LIMITS, portkey_model,
)
from backend.models import AgentName, AgentReport, DelegationResult, TeamDeps
from backend.shop_mcp import toolset_for

PROMPT_PLACEHOLDER = "<!-- PROMPT NOT WRITTEN YET -->"

# Every role can see the board and move tickets.
BOARD_TOOLS = frozenset({
    "get_shop_date", "list_open_tickets", "list_tickets", "get_ticket_details", "update_ticket_status",
})


class PromptNotWrittenError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentRole:
    name: AgentName
    title: str
    description: str           # one line other agents see when choosing who to delegate to
    prompt_file: str           # file in backend/prompts/
    mcp_tools: frozenset[str]  # MCP tools this role may call (in addition to BOARD_TOOLS)

    @property
    def all_tools(self) -> frozenset[str]:
        return BOARD_TOOLS | self.mcp_tools

    def load_prompt(self) -> str:
        text = (PROMPTS_DIR / self.prompt_file).read_text()
        if PROMPT_PLACEHOLDER in text:
            raise PromptNotWrittenError(
                f"backend/prompts/{self.prompt_file} still has the placeholder. Write the {self.title} prompt first."
            )
        return text


# --------------------------------------------------------------------------- #
# Building agents
# --------------------------------------------------------------------------- #

_agents: dict[AgentName, Agent[TeamDeps, AgentReport]] = {}


def _roles() -> dict[AgentName, AgentRole]:
    from backend.agents import ROLES  # late import: roles module imports this one
    return ROLES


def _operating_context(role: AgentRole, deps: TeamDeps) -> str:
    """Facts the system adds to every prompt so the model knows its tools and teammates."""
    roles = _roles()
    teammates = "\n".join(
        f"- `{r.name}` ({r.title}): {r.description}"
        for r in roles.values() if r.name != role.name
    )
    blocked = [n for n in deps.chain if n != role.name]
    can_delegate = deps.depth < MAX_DELEGATION_DEPTH
    lines = [
        "## Operating context (added by the system)",
        f"- You are the **{role.title}** agent (`{role.name}`). Model: {MODEL_NAME}.",
        f"- Your MCP tools: {', '.join(sorted(role.all_tools))}, plus `delegate_task`.",
        "- All shop facts must come from these tools. If a tool doesn't return it, you don't know it.",
        f"- Delegation chain so far: {' -> '.join(deps.chain)} (depth {deps.depth} of max {MAX_DELEGATION_DEPTH}).",
        (f"- You may delegate with `delegate_task` to any teammate except {', '.join(blocked)} (already upstream in this chain)."
         if blocked and can_delegate else
         "- You may delegate with `delegate_task` to any teammate." if can_delegate else
         "- Max delegation depth reached: finish the work yourself and report back."),
        "- Teammates:",
        teammates,
    ]
    if deps.ticket_id is not None:
        lines.append(f"- Ticket in focus: #{deps.ticket_id}.")
    lines.append(f'- Finish with an AgentReport where agent="{role.name}".')
    return "\n".join(lines)


def build_agent(role: AgentRole) -> Agent[TeamDeps, AgentReport]:
    agent: Agent[TeamDeps, AgentReport] = Agent(
        portkey_model(),
        name=role.name,
        deps_type=TeamDeps,
        output_type=AgentReport,
        instructions=role.load_prompt(),
        toolsets=[toolset_for(role.all_tools)],
        model_settings=MODEL_SETTINGS,
        retries=AGENT_RETRIES,
    )

    @agent.instructions
    def operating_context(ctx: RunContext[TeamDeps]) -> str:
        return _operating_context(role, ctx.deps)

    @agent.tool
    async def delegate_task(
        ctx: RunContext[TeamDeps], to_agent: AgentName, task: str, ticket_id: int | None = None
    ) -> DelegationResult:
        """Hand a specific piece of work to another agent and wait for its AgentReport.

        Args:
            to_agent: boss, inventory, accounting, facilities, or customer_service.
            task: exactly what you need done or answered, including the ticket id and any facts you already found.
            ticket_id: the ticket this work is for, if any.
        """
        return await delegate(ctx, to_agent, task, ticket_id)

    @agent.output_validator
    def stamp_agent(ctx: RunContext[TeamDeps], report: AgentReport) -> AgentReport:
        report.agent = role.name  # the report always names the agent that wrote it
        return report

    return agent


def get_agent(name: AgentName) -> Agent[TeamDeps, AgentReport]:
    if name not in _agents:
        _agents[name] = build_agent(_roles()[name])
    return _agents[name]


# --------------------------------------------------------------------------- #
# Delegation (full mesh)
# --------------------------------------------------------------------------- #

async def delegate(
    ctx: RunContext[TeamDeps], to_agent: AgentName, task: str, ticket_id: int | None
) -> DelegationResult:
    d = ctx.deps
    ticket_id = ticket_id if ticket_id is not None else d.ticket_id
    error = None
    if to_agent not in _roles():
        error = f"Unknown agent '{to_agent}'."
    elif to_agent == d.agent:
        error = "You can't delegate to yourself; do the work directly."
    elif to_agent in d.chain:
        error = (f"{to_agent} is already upstream in this chain ({' -> '.join(d.chain)}). "
                 "Return your findings in your report instead of delegating back.")
    elif d.depth >= MAX_DELEGATION_DEPTH:
        error = f"Max delegation depth ({MAX_DELEGATION_DEPTH}) reached; finish the work yourself."

    audit.append_event(
        "delegation",
        team_run_id=d.team_run_id, from_agent=d.agent, from_agent_run_id=d.agent_run_id,
        to_agent=to_agent, task=task, ticket_id=ticket_id, depth=d.depth + 1,
        allowed=error is None, refused_reason=error,
    )
    if error:
        return DelegationResult(to_agent=to_agent, ok=False, error=error)

    try:
        report = await run_agent(
            to_agent, task,
            team_run_id=d.team_run_id, usage=ctx.usage, depth=d.depth + 1,
            chain=d.chain, ticket_id=ticket_id, parent_agent_run_id=d.agent_run_id,
        )
        return DelegationResult(to_agent=to_agent, ok=True, report=report)
    except UsageLimitExceeded:
        raise  # the team budget is shared; stop everyone
    except Exception as exc:  # noqa: BLE001 - report the failure to the delegating agent
        return DelegationResult(to_agent=to_agent, ok=False, error=f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- #
# The agent loop, with one audit event per step
# --------------------------------------------------------------------------- #

def _describe_request(request: ModelRequest) -> list[dict[str, Any]]:
    parts = []
    for p in request.parts:
        if isinstance(p, ToolReturnPart):
            parts.append({"kind": "tool_result", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                          "content": p.model_response_str()})
        elif isinstance(p, RetryPromptPart):
            parts.append({"kind": "retry", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                          "content": p.model_response()})
        elif isinstance(p, UserPromptPart):
            parts.append({"kind": "user_prompt", "content": p.content})
        elif isinstance(p, SystemPromptPart):
            parts.append({"kind": "system_prompt", "sha256": hashlib.sha256(p.content.encode()).hexdigest()[:16]})
        else:
            parts.append({"kind": type(p).__name__})
    return parts


def _describe_response(response: ModelResponse) -> dict[str, Any]:
    parts = []
    for p in response.parts:
        if isinstance(p, ToolCallPart):
            parts.append({"kind": "tool_call", "tool": p.tool_name, "tool_call_id": p.tool_call_id, "args": p.args_as_dict()})
        elif isinstance(p, TextPart):
            parts.append({"kind": "text", "content": p.content})
        elif isinstance(p, ThinkingPart):
            parts.append({"kind": "thinking", "chars": len(p.content or "")})
        else:
            parts.append({"kind": type(p).__name__})
    u = response.usage
    return {
        "model_name": response.model_name,
        "finish_reason": response.finish_reason,
        "usage": {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens},
        "parts": parts,
    }


async def run_agent(
    name: AgentName,
    task: str,
    *,
    team_run_id: str,
    usage: RunUsage,
    depth: int = 0,
    chain: list[AgentName] | None = None,
    ticket_id: int | None = None,
    parent_agent_run_id: str | None = None,
) -> AgentReport:
    """Run one agent's loop to completion, auditing every step."""
    agent = get_agent(name)
    deps = TeamDeps(
        team_run_id=team_run_id, agent_run_id=uuid.uuid4().hex[:12], agent=name,
        depth=depth, chain=[*(chain or []), name], ticket_id=ticket_id,
    )
    base = {"team_run_id": team_run_id, "agent_run_id": deps.agent_run_id, "agent": name, "depth": depth}
    prompt_sha = hashlib.sha256((PROMPTS_DIR / _roles()[name].prompt_file).read_bytes()).hexdigest()[:16]
    audit.append_event(
        "agent_started", **base, parent_agent_run_id=parent_agent_run_id, chain=deps.chain,
        ticket_id=ticket_id, task=task, model=MODEL_NAME, prompt_file=_roles()[name].prompt_file,
        prompt_sha256=prompt_sha, tools=sorted(_roles()[name].all_tools) + ["delegate_task"],
    )

    step = 0
    try:
        async with agent.iter(task, deps=deps, usage=usage, usage_limits=TEAM_USAGE_LIMITS) as run:
            async for node in run:
                step += 1
                if Agent.is_user_prompt_node(node):
                    audit.append_event("step", **base, step=step, node="user_prompt", user_prompt=node.user_prompt)
                elif Agent.is_model_request_node(node):
                    audit.append_event("step", **base, step=step, node="model_request",
                                       parts=_describe_request(node.request))
                elif Agent.is_call_tools_node(node):
                    audit.append_event("step", **base, step=step, node="model_response",
                                       **_describe_response(node.model_response))
                elif Agent.is_end_node(node):
                    audit.append_event("step", **base, step=step, node="end", output=node.data.output)
            report = run.result.output
    except Exception as exc:
        audit.append_event("agent_failed", **base, step=step, error=f"{type(exc).__name__}: {exc}",
                           team_usage=_usage_dict(usage))
        raise

    audit.append_event("agent_finished", **base, steps=step, outcome=report.outcome,
                       team_usage=_usage_dict(usage))
    return report


def _usage_dict(usage: RunUsage) -> dict[str, int]:
    return {
        "model_requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }
