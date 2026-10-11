"""Campus Customs backend: FastAPI routes for the React dashboard.

Start it from the backend/ folder:
    uvicorn main:app --reload --port 8000

Every shop fact comes from the campus-customs MCP server (no direct SQL here).
Agents only *prepare* payments; the approve route below is the only thing that
moves cash, and it runs on a human's click.
"""

import asyncio
import os
import shutil
import sys
import uuid
from pathlib import Path

# Started from backend/, so make the project root importable for `backend.*`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit  # noqa: E402
from backend.agents import ROLES  # noqa: E402
from backend.agents.base import PromptNotWrittenError  # noqa: E402
from backend.config import MODEL_NAME, ORIGINAL_DB_PATH, WORKING_DB_PATH  # noqa: E402
from backend.models import TeamRunRequest  # noqa: E402
from backend.shop_mcp import call_human_tool, call_tool  # noqa: E402
from backend.team import run_team  # noqa: E402

app = FastAPI(title="Campus Customs backend", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One team run at a time: they share the working DB and the token budget.
_runs: dict[str, dict] = {}
_active_run: str | None = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

async def _mcp(tool: str, args: dict | None = None):
    data = await call_tool(tool, args or {})
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


def _ready_to_run() -> str | None:
    """Return a reason the team can't run yet, or None."""
    if not os.getenv("PORTKEY_API_KEY"):
        return "PORTKEY_API_KEY is missing. Add it to Homework 5/.env (see .env.example)."
    for role in ROLES.values():
        try:
            role.load_prompt()
        except PromptNotWrittenError as exc:
            return str(exc)
    return None


def _last_run_for(ticket_id: int) -> dict | None:
    """Latest team run for a ticket, from the audit trail (survives server restarts)."""
    started = finished = None
    for e in audit.read_events():
        if e.get("event") == "team_run_started" and e.get("ticket_id") == ticket_id:
            started, finished = e, None
        elif started and e.get("event") == "team_run_finished" and e.get("team_run_id") == started["team_run_id"]:
            finished = e
    if not started:
        return None
    return {"team_run_id": started["team_run_id"], "started_at": started["logged_at"],
            "finished": finished is not None, "ok": finished.get("ok") if finished else None}


async def _resolve_if_clear(ticket_id: int, why: str) -> bool:
    """Mark a ticket resolved once its team run is done and nothing waits on a human."""
    pending = (await _mcp("list_approvals", {"status": "pending", "ticket_id": ticket_id}))["approvals"]
    if pending:
        return False
    ticket = (await _mcp("get_ticket_details", {"ticket_id": ticket_id}))["ticket"]
    if ticket["status"] in {"resolved", "blocked"}:
        return ticket["status"] == "resolved"
    await _mcp("update_ticket_status", {"ticket_id": ticket_id, "status": "resolved", "note": why})
    audit.append_event("ticket_resolved", ticket_id=ticket_id, reason=why)
    return True


def _feed_item(e: dict) -> dict | None:
    """Turn a raw audit event into a board-friendly line: who, what they said, which tools."""
    kind, base = e.get("event"), {
        "time": e.get("logged_at"), "team_run_id": e.get("team_run_id"),
        "agent": e.get("agent"), "event": e.get("event"),
    }
    if kind == "step" and e.get("node") == "model_response":
        said = " ".join(p["content"] for p in e.get("parts", []) if p.get("kind") == "text").strip()
        tools = [{"tool": p["tool"], "args": p.get("args")} for p in e.get("parts", []) if p.get("kind") == "tool_call"]
        return {**base, "said": said, "tools": tools, "model": e.get("model_name")}
    if kind == "step" and e.get("node") == "model_request":
        results = [{"tool": p["tool"], "result": p.get("content")} for p in e.get("parts", []) if p.get("kind") == "tool_result"]
        return {**base, "tool_results": results} if results else None
    if kind == "step" and e.get("node") == "end":
        out = e.get("output") or {}
        return {**base, "said": out.get("summary", ""), "outcome": out.get("outcome"), "report": out}
    if kind == "delegation":
        return {**base, "agent": e.get("from_agent"), "to_agent": e.get("to_agent"), "said": e.get("task"),
                "allowed": e.get("allowed"), "refused_reason": e.get("refused_reason")}
    if kind in {"team_run_started", "team_run_finished", "agent_started", "agent_finished", "agent_failed",
                "human_decision", "database_reset", "ticket_resolved"}:
        return {**base, **{k: e.get(k) for k in ("ticket_id", "task", "outcome", "error", "ok", "approval_id",
                                                 "decision", "decided_by", "result", "reason") if k in e}}
    return None


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.get("/api/health")
async def health():
    return {"ok": True, "model": MODEL_NAME, "ready_to_run": _ready_to_run() is None, "not_ready_reason": _ready_to_run()}


@app.get("/api/tickets")
async def get_tickets():
    """All tickets on the board, each marked open or resolved."""
    data = await _mcp("list_tickets")
    pending = (await _mcp("list_approvals", {"status": "pending"}))["approvals"]
    running_ticket = _runs[_active_run]["ticket_id"] if _active_run else None
    tickets = []
    for t in data["tickets"]:
        resolved = t["status"] == "resolved"
        if t["id"] == running_ticket:
            phase = "running"
        elif resolved:
            phase = "resolved"
        elif any(a["ticket_id"] == t["id"] for a in pending):
            phase = "awaiting_approval"
        else:
            phase = "open"
        tickets.append({**t, "state": "resolved" if resolved else "open", "phase": phase,
                        "last_run": _last_run_for(t["id"])})
    return {"date_today": data["date_today"], "tickets": tickets}


class RunBody(BaseModel):
    instructions: str = ""


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, body: RunBody | None = None):
    """Start the agent team (Boss first) on one ticket. Poll /api/runs/{id} or /api/events for progress."""
    global _active_run
    await _mcp("get_ticket_details", {"ticket_id": ticket_id})  # 400 if the ticket doesn't exist
    reason = _ready_to_run()
    if reason:
        raise HTTPException(status_code=409, detail=reason)
    if _active_run:
        raise HTTPException(status_code=409, detail=f"Team run {_active_run} is still going; wait for it to finish.")

    team_run_id = uuid.uuid4().hex[:12]
    _runs[team_run_id] = {"team_run_id": team_run_id, "ticket_id": ticket_id, "status": "running", "result": None}
    _active_run = team_run_id

    async def _go():
        global _active_run
        try:
            result = await run_team(
                TeamRunRequest(ticket_id=ticket_id, instructions=(body.instructions if body else "")),
                team_run_id=team_run_id,
            )
            _runs[team_run_id].update(status="finished" if result.ok else "failed", result=result.model_dump(mode="json"))
            if result.ok:
                _runs[team_run_id]["resolved"] = await _resolve_if_clear(
                    ticket_id, f"Team run {team_run_id} finished with nothing waiting on a human.")
        except Exception as exc:  # noqa: BLE001
            _runs[team_run_id].update(status="failed", result={"error": f"{type(exc).__name__}: {exc}"})
        finally:
            _active_run = None

    asyncio.create_task(_go())
    return _runs[team_run_id]


@app.get("/api/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int):
    """Short per-agent summary of the latest team run on a ticket: what each agent did and which tools it used."""
    details = await _mcp("get_ticket_details", {"ticket_id": ticket_id})
    last = _last_run_for(ticket_id)
    agents: dict[str, dict] = {}
    delegations, usage = [], None
    if last:
        for e in audit.read_events():
            if e.get("team_run_id") != last["team_run_id"]:
                continue
            name = e.get("agent")
            if e.get("event") == "agent_started":
                a = agents.setdefault(name, {"agent": name, "tasks": [], "tools": [], "summary": "", "outcome": None,
                                             "actions_taken": [], "steps": 0})
                a["tasks"].append(e.get("task"))
            elif e.get("event") == "step" and name in agents:
                agents[name]["steps"] += 1
                if e.get("node") == "model_response":
                    for p in e.get("parts", []):
                        if p.get("kind") == "tool_call" and p["tool"] not in agents[name]["tools"]:
                            agents[name]["tools"].append(p["tool"])
                elif e.get("node") == "end":
                    out = e.get("output") or {}
                    agents[name].update(summary=out.get("summary", ""), outcome=out.get("outcome"),
                                        actions_taken=out.get("actions_taken", []))
            elif e.get("event") == "delegation":
                delegations.append({"from": e.get("from_agent"), "to": e.get("to_agent"), "task": e.get("task"),
                                    "allowed": e.get("allowed")})
            elif e.get("event") == "team_run_finished":
                usage = {k: e.get(k) for k in ("model_requests", "tool_calls", "input_tokens", "output_tokens")}
    return {"ticket": details["ticket"], "linked": details["linked"], "last_run": last,
            "agents": list(agents.values()), "delegations": delegations, "usage": usage}


@app.get("/api/runs/{team_run_id}")
async def get_run(team_run_id: str):
    """Status and final report of a team run started by this server."""
    if team_run_id not in _runs:
        raise HTTPException(status_code=404, detail="Unknown team run id.")
    return _runs[team_run_id]


@app.get("/api/events")
async def get_events(
    limit: int = Query(100, ge=1, le=1000),
    team_run_id: str | None = None,
    raw: bool = False,
):
    """Recent agent events, newest first: what each agent said and which tools it used."""
    events = audit.read_events()
    if team_run_id:
        events = [e for e in events if e.get("team_run_id") == team_run_id]
    if not raw:
        events = [f for f in (_feed_item(e) for e in events) if f]
    return {"active_run": _active_run, "events": list(reversed(events))[:limit]}


@app.get("/api/approvals")
async def get_approvals(status: str = ""):
    """Payment requests the agents prepared (default: all; ?status=pending for the approval queue)."""
    return await _mcp("list_approvals", {"status": status})


class DecisionBody(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human making the decision.")
    reason: str = ""


@app.post("/api/approvals/{approval_id}/approve")
async def approve_payment(approval_id: int, body: DecisionBody):
    """Human clicked Approve: pay it. This is the only route that changes cash."""
    result = await call_human_tool("approve_and_pay", {"approval_id": approval_id, "approved_by": body.approved_by})
    ok = not (isinstance(result, dict) and "error" in result)
    audit.append_event("human_decision", approval_id=approval_id, decision="approve", decided_by=body.approved_by,
                       ok=ok, result=result)
    if not ok:
        raise HTTPException(status_code=400, detail=result["error"])
    ticket_id = result["approval"]["ticket_id"]
    result["ticket_resolved"] = await _resolve_if_clear(
        ticket_id, f"Payment approval #{approval_id} paid by {body.approved_by}; nothing left waiting on a human.")
    return result


@app.post("/api/approvals/{approval_id}/reject")
async def reject_payment(approval_id: int, body: DecisionBody):
    """Human clicked Reject: no money moves."""
    result = await call_human_tool(
        "reject_approval", {"approval_id": approval_id, "decided_by": body.approved_by, "reason": body.reason}
    )
    ok = not (isinstance(result, dict) and "error" in result)
    audit.append_event("human_decision", approval_id=approval_id, decision="reject", decided_by=body.approved_by,
                       ok=ok, result=result)
    if not ok:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/drafts")
async def get_drafts(ticket_id: int = 0):
    """Draft messages on the board (never sent)."""
    return await _mcp("list_drafts", {"ticket_id": ticket_id})


@app.get("/api/cash")
async def get_cash():
    """Current checking balance from cash_accounts (plus what's waiting for approval)."""
    data = await _mcp("get_cash_balance")
    checking = next((a for a in data["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="No 'checking' account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "pending_approval_total": data["pending_approval_total"],
        "balance_if_all_pending_paid": data["balance_if_all_pending_paid"],
    }


@app.post("/api/reset")
async def reset_database():
    """Copy data/campus_customs.db over data/campus_customs_new.db. The audit trail is kept."""
    if _active_run:
        raise HTTPException(status_code=409, detail="Can't reset while a team run is going.")
    shutil.copyfile(ORIGINAL_DB_PATH, WORKING_DB_PATH)
    _runs.clear()
    audit.append_event("database_reset", source=ORIGINAL_DB_PATH.name, target=WORKING_DB_PATH.name)
    return {"ok": True, "message": f"{WORKING_DB_PATH.name} reset from {ORIGINAL_DB_PATH.name}."}
