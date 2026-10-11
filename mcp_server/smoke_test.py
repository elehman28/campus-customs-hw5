"""Smoke-test the Campus Customs MCP server over the real MCP protocol.

Launches the server exactly as configured in .mcp.json (stdio), calls each
tool, then checks every result against data/campus_customs_new.db read
directly with sqlite3. Writes the evidence to output/mcp_smoke.json.

Run:  .venv/bin/python mcp_server/smoke_test.py
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
MCP_CONFIG = json.loads((ROOT / ".mcp.json").read_text())
_server = MCP_CONFIG["mcpServers"]["campus-customs"]
_server["command"] = str(ROOT / _server["command"])
_server["args"] = [str(ROOT / a) for a in _server["args"]]
_server["cwd"] = str(ROOT)
DB_PATH = ROOT / _server["env"]["CAMPUS_CUSTOMS_DB"]
_server["env"]["CAMPUS_CUSTOMS_DB"] = str(DB_PATH)
OUT_PATH = ROOT / "output" / "mcp_smoke.json"

TESTS = [
    {
        "prompt": "Using the campus-customs MCP server, show me every open ticket on the board and today's shop date.",
        "tool": "list_open_tickets",
        "arguments": {},
    },
    {
        "prompt": "Get the full details for ticket 101, including the stock, pricing, invoice, and vendor it links to.",
        "tool": "get_ticket_details",
        "arguments": {"ticket_id": 101},
    },
    {
        # Re-asserts the current status with no note, so the working DB is
        # exercised through the write path but left unchanged.
        "prompt": "Set ticket 102 to status 'open' (its current status) with no note, to confirm the update tool works without changing anything.",
        "tool": "update_ticket_status",
        "arguments": {"ticket_id": 102, "status": "open", "note": ""},
    },
]


def db_rows(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def db_one(sql, params=()):
    rows = db_rows(sql, params)
    return rows[0] if rows else None


def expected_from_db(tool, args):
    """Build what each tool *should* return straight from the database."""
    today = db_one("SELECT date_today FROM desk LIMIT 1")["date_today"]
    if tool == "list_open_tickets":
        tickets = db_rows("SELECT * FROM tickets WHERE status='open' ORDER BY created_at, id")
        return {"date_today": today, "count": len(tickets), "tickets": tickets}
    if tool == "get_ticket_details":
        t = db_one("SELECT * FROM tickets WHERE id=?", (args["ticket_id"],))
        inv = db_one("SELECT * FROM invoices WHERE id=?", (t["invoice_id"],))
        return {
            "date_today": today,
            "ticket": t,
            "linked": {
                "inventory": db_rows("SELECT * FROM inventory WHERE sku=? ORDER BY size", (t["sku"],)),
                "requested_size_stock": db_one(
                    "SELECT * FROM inventory WHERE sku=? AND size=?", (t["sku"], t["size"])
                ),
                "pricing": db_one("SELECT * FROM pricing WHERE sku=?", (t["sku"],)),
                "invoice": inv,
                "vendor": db_one("SELECT * FROM vendors WHERE id=?", (inv["vendor_id"],)),
            },
        }
    if tool == "update_ticket_status":
        t = db_one("SELECT * FROM tickets WHERE id=?", (args["ticket_id"],))
        return {"previous_status": "open", "ticket": t}
    raise ValueError(tool)


async def main():
    results = []
    async with Client(MCP_CONFIG) as client:
        listed = [t.name for t in await client.list_tools()]
        for test in TESTS:
            res = await client.call_tool(test["tool"], test["arguments"])
            output = res.structured_content
            if isinstance(output, dict) and set(output) == {"result"}:
                output = output["result"]
            expected = expected_from_db(test["tool"], test["arguments"])
            results.append(
                {
                    "prompt": test["prompt"],
                    "tool": test["tool"],
                    "arguments": test["arguments"],
                    "output": output,
                    "matches_database": output == expected,
                }
            )

    evidence = {
        "server": "campus-customs",
        "transport": "stdio (launched from .mcp.json)",
        "database": str(DB_PATH.relative_to(ROOT)),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tools_advertised_by_server": listed,
        "all_match_database": all(r["matches_database"] for r in results),
        "tests": results,
    }
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(evidence, indent=2) + "\n")
    for r in results:
        print(f"{r['tool']:<22} matches_database={r['matches_database']}")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
