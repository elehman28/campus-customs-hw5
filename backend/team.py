"""Team entry point: a human starts the Boss on one ticket or the whole board.

The Boss delegates from there. Every agent shares one usage budget
(TEAM_USAGE_LIMITS), so the whole team run stops if it gets too expensive.
"""

import asyncio
import uuid

from pydantic_ai.usage import RunUsage

from backend import audit
from backend.agents import run_agent
from backend.config import MODEL_NAME, TEAM_RUN_TIMEOUT_SECONDS, TEAM_USAGE_LIMITS
from backend.models import TeamRunRequest, TeamRunResult
from backend.shop_mcp import SHOP_TOOLSET


def _boss_task(req: TeamRunRequest) -> str:
    if req.ticket_id is not None:
        task = f"Work ticket #{req.ticket_id} on the Campus Customs board until it is resolved or waiting on a human."
    else:
        task = "Work every open ticket on the Campus Customs board until each is resolved or waiting on a human."
    if req.instructions.strip():
        task += f"\n\nInstructions from the human operator: {req.instructions.strip()}"
    return task


async def run_team(req: TeamRunRequest, team_run_id: str | None = None) -> TeamRunResult:
    team_run_id = team_run_id or uuid.uuid4().hex[:12]
    usage = RunUsage()
    audit.append_event(
        "team_run_started", team_run_id=team_run_id, ticket_id=req.ticket_id,
        instructions=req.instructions, model=MODEL_NAME,
        limits={
            "request_limit": TEAM_USAGE_LIMITS.request_limit,
            "tool_calls_limit": TEAM_USAGE_LIMITS.tool_calls_limit,
            "total_tokens_limit": TEAM_USAGE_LIMITS.total_tokens_limit,
            "timeout_seconds": TEAM_RUN_TIMEOUT_SECONDS,
        },
    )
    report, error = None, None
    try:
        async with SHOP_TOOLSET:  # one MCP server process shared by every agent in this run
            report = await asyncio.wait_for(
                run_agent("boss", _boss_task(req), team_run_id=team_run_id, usage=usage, ticket_id=req.ticket_id),
                timeout=TEAM_RUN_TIMEOUT_SECONDS,
            )
    except Exception as exc:  # noqa: BLE001 - surface every failure in the result + audit trail
        error = f"{type(exc).__name__}: {exc}"

    result = TeamRunResult(
        team_run_id=team_run_id, ok=error is None, report=report, error=error,
        model_requests=usage.requests, tool_calls=usage.tool_calls,
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
    )
    audit.append_event("team_run_finished", **result.model_dump(mode="json"))
    return result
