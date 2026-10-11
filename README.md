# Campus Customs: Multi-Agent Operations (Homework 5)

An agent team runs the **Campus Customs** shop. Open tickets (custom orders, rent, unpaid bills, discount requests) land on a board. Five PydanticAI agents work them through an MCP server, and a human watches and approves payments on a React dashboard.

```
React dashboard (frontend/, :5173)  →  FastAPI backend (backend/main.py, :8000)  →  agent team (backend/agents/)
                                                      │                                   │
                                                      └──────── MCP server (mcp_server/server.py) ────────┘
                                                                           │
                                                              data/campus_customs_new.db
```

- **Agents:** Boss, Inventory, Accounting, Facilities and Customer Service. They're fully connected: any agent can `delegate_task` to any other.
- **Model:** every agent uses **`gpt-6-luna` through Portkey** (`PORTKEY_API_KEY`). It's fixed in `backend/config.py`.
- **Shop data:** only through MCP tools over `data/campus_customs_new.db`.
- **Money:** agents only *request* payments. A human approves them on the dashboard, and that is the only path that changes cash.

## Layout
```
AI_prompts.md          every prompt typed while vibe coding, one section per problem
requirements.txt       Python dependencies
.env.example           copy to .env and add PORTKEY_API_KEY (.env is git-ignored)
.mcp.json              MCP server registration (campus-customs, stdio)
data/
  campus_customs.db       ORIGINAL: never modified, the reset source
  campus_customs_new.db   WORKING COPY: what the MCP server reads/writes (state after the graded run)
mcp_server/            server.py (FastMCP, 22 tools), smoke_test.py, README.md
backend/               main.py (FastAPI), models.py, config.py, team.py, audit.py, shop_mcp.py,
                       agents/ (boss, inventory, accounting, facilities, customer_service), prompts/ (one .md per agent)
frontend/              React + Vite + TypeScript dashboard
output/                harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json,
                       resolved_board.html, audit_trail.json, github_url.txt
```

## Setup (once)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # then put your PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

## 1. Copy the original DB to the working copy (whenever you need a clean run)
`data/campus_customs.db` is never changed. To start fresh, copy it over the working copy:
```bash
cp data/campus_customs.db data/campus_customs_new.db
```
You can also use the dashboard's **↺ Reset shop** button or `curl -X POST http://localhost:8000/api/reset`. Either one does the same copy and keeps the audit trail.

## 2. Start the MCP server
The MCP server is registered in `.mcp.json`, and the backend launches it automatically over stdio. To run or check it on its own:
```bash
.venv/bin/python mcp_server/server.py          # run the server (stdio)
.venv/bin/python mcp_server/smoke_test.py      # call each tool and compare with the DB → output/mcp_smoke.json
```
Claude Code also picks up `.mcp.json` when opened in this folder.

## 3. Start the FastAPI backend
```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```
Runs at http://localhost:8000 (docs at `/docs`). CORS allows the Vite page at `http://localhost:5173`.

## 4. Start the React board
```bash
cd frontend
npm run dev
```
Opens http://localhost:5173. It talks to the backend at `http://localhost:8000` (set in `frontend/.env`, copied from `frontend/.env.example`). On the board:
1. Pick a ticket.
2. Press **Run the team** and watch the agents on the floor and the live wire.
3. Type your name under **Signing as** and press **Approve & pay** on each cheque.
4. Watch checking drop and the ticket get stamped **Resolved**.

## 5. Reset the DB before a full 3-ticket run
Always start a full run over tickets 101, 102 and 103 from a clean database:
```bash
cp data/campus_customs.db data/campus_customs_new.db     # or ↺ Reset shop on the board
```
Then run 101, 102 and 103 from the board and approve the payments. Expected cash for a full run: **$3,400.00 − $840.00 (invoice 501) − $2,400.00 (rent) = $160.00**.

There's also a command-line runner: `.venv/bin/python -m backend.run_team --reset --ticket 101`.

## Shop rules (enforced in code)
- `desk.date_today` (2026-08-31) is "today", and vendor lead times come from `vendors`.
- A vendor won't ship while it has an open unpaid invoice (`check_vendor_can_ship`).
- Every payment needs human approval. `approve_and_pay` is hidden from agents and updates `cash_accounts`, `payments` and the invoice or lease.
- No negative balances: the pay tool refuses if there isn't enough cash. Cash only goes out.
- No emails or calls: customer, vendor and landlord messages are saved as drafts only.

## What the graded run produced
See `output/desk_tickets.html` (Expected vs Actual, Cash, Reflection), `output/resolved_tickets.json`, `output/resolved_board.html` and `output/audit_trail.json`. `data/campus_customs_new.db` is committed in its post-run state: tickets 101–103 resolved, two payments approved by Elise, and checking at **$160.00**.
