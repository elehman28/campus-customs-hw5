# Campus Customs — Agent Harness

Reference notes for the Campus Customs multi-agent team (Boss, Inventory, Accounting, Facilities, Customer Service). This file will keep growing as the homework progresses.

- **Original DB (reset source, never modified):** `data/campus_customs.db`
- **Working DB (MCP server + backend read/write here):** `data/campus_customs_new.db`

---

## Database tables

### `desk`
Fields: `date_today` (TEXT), `notes` (TEXT)
**Why it matters:** `date_today` is the shop's "today" (2026-08-31). Agents use it, not the real clock, to decide what's overdue or due soon.

### `tickets`
Fields: `id` (INTEGER PK), `type` (TEXT), `requester` (TEXT), `subject` (TEXT), `sku` (TEXT), `size` (TEXT), `qty` (INTEGER), `lease_id` (INTEGER → leases.id), `invoice_id` (INTEGER → invoices.id), `status` (TEXT), `notes` (TEXT), `created_at` (TEXT)
**Why it matters:** This is the work board. Each open ticket is a job the Boss assigns, and its foreign keys point to the rows the other agents need.

### `inventory`
Fields: `sku` (TEXT), `name` (TEXT), `size` (TEXT), `qty` (INTEGER), `location` (TEXT); PK = (`sku`, `size`)
**Why it matters:** The Inventory agent checks stock per SKU and size before promising a customer order or a bulk deal.

### `pricing`
Fields: `sku` (TEXT PK), `unit_cost` (REAL), `list_price` (REAL)
**Why it matters:** Gives the margin floor (cost) and normal price that Accounting and Customer Service use to judge discount requests.

### `vendors`
Fields: `id` (INTEGER PK), `name` (TEXT), `specialty` (TEXT), `lead_days` (INTEGER)
**Why it matters:** Tells Inventory which vendor restocks an item and how many days a reorder takes (lead times come only from this table).

### `invoices`
Fields: `id` (INTEGER PK), `vendor_id` (INTEGER → vendors.id), `amount` (REAL), `due_date` (TEXT), `status` (TEXT), `description` (TEXT)
**Why it matters:** Accounting tracks unpaid vendor bills here. A vendor with an open unpaid invoice won't ship new product.

### `leases`
Fields: `id` (INTEGER PK), `space_name` (TEXT), `landlord` (TEXT), `monthly_rent` (REAL), `next_due` (TEXT), `notes` (TEXT)
**Why it matters:** Facilities uses it to know how much rent is owed, to whom, and when.

### `cash_accounts`
Fields: `name` (TEXT PK), `balance` (REAL), `date` (TEXT)
**Why it matters:** This is the only source of cash (checking = $3,400). The pay tool must refuse any payment that would push the balance negative, and no money ever comes in.

### `payments`
Fields: `id` (INTEGER PK), `kind` (TEXT), `ref_id` (INTEGER), `amount` (REAL), `account` (TEXT), `paid_at` (TEXT), `approved_by` (TEXT)
**Why it matters:** Audit log of every payment (starts empty). Each row must record the human who approved it.

---

## How the open tickets link to the tables

| Ticket | Type | Links | What the agents find |
|---|---|---|---|
| **101** Tauhid Zaman: "Bulldog tee" | `customer_order` | `sku`=CC-TEE-WHITE, `size`=S, `qty`=1 → `inventory`; `invoice_id`=501 → `invoices` → `vendors` | Stock for CC-TEE-WHITE S is **0**. Restock comes from Bulldog Print Co (vendor 1, 5 lead days), but invoice 501 ($840, due 2026-08-28) is **open and overdue**, so the vendor won't ship until it's paid (needs human approval). |
| **102** Elm City Properties: "Rent due" | `rent_notice` | `lease_id`=1 → `leases` | Chapel Street shop rent is **$2,400**, due **2026-09-02** (2 days after `date_today`). Paying it comes out of `cash_accounts` and needs human approval. |
| **103** Yale AI Club: "Bulk hoodie discount" | `price_override` | `sku`=CC-HOOD-NAVY, `size`=M, `qty`=20 → `inventory` + `pricing` | Only **8** are in stock (short by 12). Cost is $22 and list price is $58, so any discount has to stay above cost. |

**Cash check:** $3,400 − $840 (invoice 501) − $2,400 (rent) = **$160** left. Both payments fit, but only just.

---

## MCP server (`mcp_server/server.py`)

FastMCP server named `campus-customs`. Every agent uses these tools. It reads from and writes to `data/campus_customs_new.db` (this can be overridden with the `CAMPUS_CUSTOMS_DB` env var). Tools return only what is stored in the database and give an explicit error when a row doesn't exist. They never guess.

### Tool 1: `list_open_tickets()`
**Tables it reads:** `tickets` (rows where `status = 'open'`) and `desk` (`date_today`)

| Ticket it unlocks | Why this tool is correct for that ticket |
|---|---|
| **101** | It shows the Boss that Tauhid Zaman's `customer_order` for CC-TEE-WHITE size S is waiting and carries `invoice_id` 501. Alongside `date_today` = 2026-08-31, that tells the Boss to send the ticket to both Inventory and Accounting. |
| **102** | It surfaces the Elm City Properties `rent_notice` with `lease_id` 1, and returns `date_today` = 2026-08-31 so Facilities can see the rent is due in 2 days. |
| **103** | It puts the Yale AI Club's `price_override` (20 × CC-HOOD-NAVY M) on the board. Because its `type` is `price_override`, the Boss knows to route it to Customer Service and Accounting rather than treating it as a normal order. |

### Tool 2: `get_ticket_details(ticket_id)`
**Tables it reads:** `tickets` + whichever linked rows exist: `inventory`, `pricing`, `invoices` → `vendors`, `leases`, and `desk`

| Ticket it unlocks | Tables read for this ticket | Why this tool is correct for that ticket |
|---|---|---|
| **101** | `inventory` (CC-TEE-WHITE S), `pricing`, `invoices` (#501), `vendors` (#1) | In one call it shows that size S has `qty` = 0, and that the only restock vendor (Bulldog Print Co, `lead_days` 5) has an $840 invoice still `open` and past its 2026-08-28 due date. That is exactly why the tee can't ship until the invoice is paid. |
| **102** | `leases` (#1) | It follows `lease_id` 1 to the Chapel Street shop lease and returns the real `monthly_rent` of $2,400 and `next_due` of 2026-09-02. Facilities can then request the exact payment amount instead of guessing it from the email text. |
| **103** | `inventory` (CC-HOOD-NAVY, all sizes), `pricing` | It shows only 8 hoodies in size M (12 short of the 20 requested), along with `unit_cost` $22 and `list_price` $58. Accounting can then set a bulk discount that stays above cost and Customer Service can say what can ship now. |

### Tool 3: `update_ticket_status(ticket_id, status, note="")`
**Tables it reads/writes:** reads `tickets` (current `status` + `notes`), writes `tickets.status` and appends to `tickets.notes`

| Ticket it unlocks | Why this tool is correct for that ticket |
|---|---|
| **101** | It can mark Tauhid's order `blocked` with a note like "S out of stock; invoice 501 unpaid." Once the payment is approved it can move to `resolved`, so the board shows why the tee is waiting. |
| **102** | After a human approves the $2,400 rent payment, it closes the Elm City Properties ticket as `resolved` and records the payment in the notes, which keeps the rent from being paid twice. |
| **103** | It can set the Yale AI Club ticket to `waiting_approval` while the discount and the 8-of-20 stock gap are checked. The note keeps the full decision trail on the ticket. |

---

## MCP connection and smoke test

- **Connection config:** `.mcp.json` at the project root registers the server `campus-customs`. It launches over stdio with `.venv/bin/python mcp_server/server.py`, and `CAMPUS_CUSTOMS_DB` points to `data/campus_customs_new.db`. Claude Code loads this file automatically when a session starts in this folder.
- **Smoke test:** `.venv/bin/python mcp_server/smoke_test.py` connects as an MCP client using that same `.mcp.json`. It calls each tool and compares the output to a direct sqlite3 read of the working DB. Evidence is in `output/mcp_smoke.json`; all 3 tools have `matches_database: true`. It was captured in Problem 4 against the clean working database, before any tickets were run.
- The `update_ticket_status` test sets ticket 102 to its current status (`open`) with no note. That exercises the write path without changing the working DB. **Only rerun the smoke test after a reset**: on the post-run database ticket 102 is `resolved`, so this test would reopen it.

---

## Agent team (Problem 5)

Built with PydanticAI. Every agent uses **`gpt-6-luna` through Portkey** (`PORTKEY_API_KEY`). The model name is a constant in `backend/config.py`, not an env var, so no other model can be swapped in. Each agent returns an `AgentReport` (`backend/models.py`).

**Full connectivity:** every agent has a `delegate_task(to_agent, task, ticket_id)` tool and can hand work to any of the other four. Two guards keep that from looping: an agent can't delegate to someone already upstream in the current chain, and the max depth is 3.

| Agent | File | Prompt | Owns | MCP tools (in addition to the board tools*) |
|---|---|---|---|---|
| **Boss** | `backend/agents/boss.py` | `backend/prompts/boss.md` | Triage, routing, checking teammates' work, final report to the human | `get_cash_balance`, `list_approvals`, `list_drafts` |
| **Inventory** | `backend/agents/inventory.py` | `backend/prompts/inventory.md` | Stock, vendors, lead times, draft reorders | `check_stock`, `get_pricing`, `list_vendors`, `check_vendor_can_ship`, `draft_vendor_reorder`, `release_held_reorders` |
| **Accounting** | `backend/agents/accounting.py` | `backend/prompts/accounting.md` | Cash, invoices, discount math, **the only role that files payment approval requests** | `get_cash_balance`, `list_invoices`, `list_payments`, `get_pricing`, `quote_bulk_price`, `check_vendor_can_ship`, `get_lease`, `request_payment_approval`, `list_approvals` |
| **Facilities** | `backend/agents/facilities.py` | `backend/prompts/facilities.md` | Shop space, lease, rent due dates, landlord drafts | `get_lease`, `list_leases`, `get_cash_balance`, `list_approvals`, `draft_message` |
| **Customer Service** | `backend/agents/customer_service.py` | `backend/prompts/customer_service.md` | Customer replies (drafts only), what can be promised | `check_stock`, `get_pricing`, `quote_bulk_price`, `draft_message`, `list_drafts` |

\*Board tools, given to every agent: `get_shop_date`, `list_open_tickets`, `list_tickets`, `get_ticket_details`, `update_ticket_status`.

**Agent loop** (`backend/agents/base.py → run_agent`): this steps through `agent.iter()` one node at a time (user prompt → model request → model response with tool calls → … → end). Every node is appended to `output/audit_trail.json`.

**Audit trail** (`output/audit_trail.json`): a JSON array that is only ever appended to and never wiped. Writes are atomic. Event types are `team_run_started`, `agent_started`, `step`, `delegation`, `agent_finished`, `agent_failed`, and `team_run_finished`. Each event records:
- `team_run_id`, `agent_run_id`, `agent`, `depth`, `step`, and a timestamp
- the prompt file and its hash, the model name the API actually reported, and the tool calls with their arguments
- tool results (truncated at 4,000 characters), delegation requests and refusals, final output, and token usage

Emails and card-like numbers are redacted before anything is written.

**Run:** `.venv/bin/python -m backend.run_team --reset --ticket 101` (leave out `--ticket` to work the whole board).

---

## All MCP tools and the tables they use

| Tool | Tables | Reads/Writes | Used by |
|---|---|---|---|
| `get_shop_date` | `desk` | R | all |
| `list_open_tickets` | `tickets`, `desk` | R | all |
| `list_tickets` | `tickets`, `desk` | R | all |
| `get_ticket_details` | `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`, `approvals`, `drafts`, `desk` | R | all |
| `update_ticket_status` | `tickets` | W | all |
| `check_stock` | `inventory` | R | Inventory, Customer Service |
| `get_pricing` | `pricing` | R | Inventory, Accounting, Customer Service |
| `list_vendors` | `vendors` | R | Inventory |
| `check_vendor_can_ship` | `vendors`, `invoices`, `desk` | R | Inventory, Accounting |
| `draft_vendor_reorder` | `drafts` (W); `vendors`, `inventory`, `invoices`, `tickets`, `desk` (R) | W | Inventory |
| `release_held_reorders` | `drafts`, `tickets` (W); `vendors`, `invoices`, `desk` (R) | W (nothing sent) | Inventory |
| `get_cash_balance` | `cash_accounts`, `approvals` | R | Boss, Accounting, Facilities |
| `list_invoices` | `invoices`, `vendors`, `desk` | R | Accounting |
| `list_payments` | `payments` | R | Accounting |
| `quote_bulk_price` | `pricing`, `inventory` | R | Accounting, Customer Service |
| `request_payment_approval` | `approvals`, `tickets` (W); `invoices`/`leases`, `vendors`, `cash_accounts`, `desk` (R) | W (no money moves) | Accounting |
| `list_approvals` | `approvals` | R | Boss, Accounting, Facilities |
| `get_lease` | `leases`, `desk` | R | Accounting, Facilities |
| `list_leases` | `leases`, `desk` | R | Facilities |
| `draft_message` | `drafts` (W); `tickets`, `desk` (R) | W (nothing sent) | Facilities, Customer Service |
| `list_drafts` | `drafts` | R | Boss, Customer Service |
| `approve_and_pay` | `cash_accounts`, `payments`, `invoices`/`leases`, `approvals`, `tickets`, `drafts` (auto-releases held reorders once a vendor's last invoice is paid) | W | **Human only** (dashboard → backend) |
| `reject_approval` | `approvals`, `tickets` | W | **Human only** (dashboard → backend) |

`approvals` and `drafts` are support tables the MCP server creates if they're missing. Resetting the database removes them, which is what we want.

---

## Safety

**Money and customers (enforced in code, not just in prompts):**
- **Human approval for every payment.** Agents can only *request* a payment (`request_payment_approval`). The tool that moves money (`approve_and_pay`) is filtered out of every agent's toolset, and it refuses approvals signed by an agent name.
- **No made-up amounts.** Payment amounts and payees come from `invoices` and `leases`, never from the model. They're re-read at pay time so a stale request can't overpay.
- **No negative balances.** Payments are refused if cash would go below $0, and the check and the deduction run in one database transaction. Requests are refused if they're over the balance, and agents get a warning when all pending requests together would overdraw the account.
- **No double payments.** A duplicate request for an item that is already pending or paid is refused.
- **Separation of duties.** Only Accounting can file payment requests. Facilities and Inventory have to route through Accounting.
- **Nothing is sent.** Customer, vendor, and landlord messages are saved as `drafts` for a human to review, and there are no email or phone tools. Vendor reorders are marked `blocked_unpaid_invoice` while the vendor has an open unpaid invoice.
- **Discounts can't go below cost.** `quote_bulk_price` marks any price at or below `unit_cost` as not allowed.
- **Least privilege and a full audit trail.** Each role sees only its own tools. Every step, tool call, delegation, and model name is logged, with emails and card-like numbers redacted.

**Token and loop limits (in `backend/config.py`):**
- One shared budget per team run, across all agents: 40 model requests, 80 tool calls, and 200,000 tokens. The run stops for everyone if any limit is hit.
- Max delegation depth is 3. Agents can't delegate to themselves or to anyone already upstream in the chain.
- Each model reply is capped at 1,500 output tokens. Each agent gets 2 retries, and the whole team run has a 300-second timeout.
- Tool results in the audit trail are truncated at 4,000 characters. Agents get the shop date and linked rows in a single `get_ticket_details` call instead of many small lookups.

---

## Backend routes (`backend/main.py`)

Start the server from `backend/` with `uvicorn main:app --reload --port 8000`, which serves `http://localhost:8000`. CORS allows the React dev server at `localhost:5173`. All shop data goes through the MCP server.

- `GET /api/health`: shows the model in use and whether the team is ready to run (Portkey key present and all five prompts written).
- `GET /api/tickets`: all tickets on the board with their raw `status`, a simple `state` of `open` or `resolved`, a dashboard `phase` (`open`, `running`, `awaiting_approval` or `resolved`) and `last_run`, plus `date_today`.
- `POST /api/tickets/{ticket_id}/run`: starts the agent team (Boss first) on one ticket in the background and returns a `team_run_id`. Returns 409 if prompts or the key are missing, or if a run is already going.
- `GET /api/tickets/{ticket_id}/summary`: a per-agent debrief of the ticket's latest run: tasks, tools used, summary, outcome, actions, hand-offs and token usage.
- `GET /api/runs/{team_run_id}`: status (`running`, `finished` or `failed`) and the final report and token usage for a team run.
- `GET /api/events?limit=&team_run_id=&raw=`: recent agent events, newest first. Shows what each agent said, which tools it called and what they returned, plus hand-offs and outcomes, so the board can refresh. Read from `output/audit_trail.json`.
- `GET /api/approvals?status=`: the payment requests agents have prepared (`?status=pending` gives the approval queue).
- `POST /api/approvals/{approval_id}/approve` with body `{"approved_by": "<human name>"}`: a human clicked Approve. Calls the human-only `approve_and_pay` MCP tool. **This is the only route that changes cash.** It refuses if cash would go negative or if the approver is an agent, and the decision is logged to the audit trail.
- `POST /api/approvals/{approval_id}/reject` with body `{"approved_by": "<human name>", "reason": "..."}`: a human clicked Reject. No money moves, and the decision is logged.
- `GET /api/drafts?ticket_id=`: draft messages on the board (customer, vendor and landlord). These are never sent.
- `GET /api/cash`: the current `checking` balance from `cash_accounts`, plus the total waiting for approval and the balance if all of it were paid.
- `POST /api/reset`: copies `data/campus_customs.db` over `data/campus_customs_new.db` to start a fresh run. Blocked while a run is going. The audit trail is kept, not wiped.

**Ticket lifecycle in the backend:** when a team run finishes, the backend marks the ticket `resolved` (through the MCP `update_ticket_status` tool) if no payment approval is pending for it and the team didn't mark it `blocked`. When a human approves the last pending payment on a ticket, `approve` also marks it `resolved`. Both write a `ticket_resolved` audit event.

---

## Model settings note (found in Problem 9)

The first real run failed with a Portkey/Azure 400 error: *"Function tools with reasoning_effort are not supported for gpt-6-luna … set reasoning_effort to 'none'."* `backend/config.py` now sends `openai_reasoning_effort="none"`, which is still `gpt-6-luna` through Portkey. The failed attempt (team run `fa3cffa06d42`) moved no money and stays in the audit trail. The database was reset again before the real run. Responses report the dated model id `gpt-6-luna-2026-09-22`.

---

## Dashboard (`frontend/`, Problem 8)

React + Vite + TypeScript. Run `npm run dev` in `frontend/` to serve it at `http://localhost:5173`. It calls `http://localhost:8000` (`VITE_API_URL` in `frontend/.env`). Full design notes are in `output/design.md`.

| Area | Component | Backend routes it calls |
|---|---|---|
| Ticket stubs: phase chips, "Resolved" stamp, x/3 progress | `TicketRail.tsx` | `GET /api/tickets` (polled every 2.5 s) |
| Selected ticket + **Run the team** | `TicketHero.tsx` | `POST /api/tickets/{id}/run`, `GET /api/health` |
| Agent floor: pentagon of agents, hand-off lines, live status and tool | `AgentFloor.tsx` | `GET /api/events?team_run_id=` (polled every 1.2 s while running) |
| Live wire: what each agent said, tool-call chips, results, hand-offs | `LiveWire.tsx` | same |
| Debrief: per-agent summary, route, tokens | `Debrief.tsx` | `GET /api/tickets/{id}/summary` |
| Checking vault: rolling balance, runway bar | `CashVault.tsx` | `GET /api/cash` |
| Approval cheques: "Signing as" + Approve & pay / Reject | `ApprovalQueue.tsx` | `GET /api/approvals?status=pending`, `POST /api/approvals/{id}/approve`, `.../reject` |
| Reset shop (needs a second click to confirm) | `Header.tsx` | `POST /api/reset` |

---

## Problem 9 run results (final graded run, expanded prompts)

The database was reset first, and the starting checking balance was **$3,400.00**.

| Ticket | Team runs | Hand-offs | Human approval | Checking | Tokens | Final |
|---|---|---|---|---|---|---|
| 101 | `4338ea3447e4` + follow-up `ce1db5469628` | Boss→Inv, Boss→Acct, Boss→CS; follow-up Boss→Inv, Boss→CS | #1 $840.00 invoice 501 (Elise) | $3,400.00 → $2,560.00 | 95,022 | resolved |
| 102 | `83c0dea08a19` | Boss→Facilities, Facilities→Accounting | #2 $2,400.00 rent lease 1 (Elise) | $2,560.00 → $160.00 | 31,865 | resolved |
| 103 | `e81e61963687` + decision `9b35ae8824f3` + follow-up `84a96fadf8fc` | Boss→Acct, Boss→Inv, Boss→CS; then Boss→Acct, Boss→CS; then Boss→Inv, Boss→CS | price decision only: 20% off, $928.00 (Elise) | $160.00 (no change) | 130,369 | resolved |

The ending checking balance of **$160.00** matches `cash_accounts` (2 payments totaling $3,240.00). Details are in `output/desk_tickets.html` (Actual, Cash and Reflection tabs), `output/resolved_tickets.json` and `output/resolved_board.html`. Every step is in `output/audit_trail.json`.

**Bug found and fixed during the run:** held reorder drafts (`blocked_unpaid_invoice`) didn't update after a human paid the vendor's invoice, so a customer draft repeated a stale "restock on hold." The fix: `approve_and_pay` now auto-releases a vendor's held reorders when its last open invoice is paid, the new `release_held_reorders` tool lets Inventory re-check, and the Boss, Inventory and Customer Service prompts now say to re-check facts after a human acts. The 101 and 103 follow-up runs used the fix.

---|---|---|---|---|---|
| 101 | Boss→Inventory, Boss→Accounting | #1 $840.00 invoice 501 (Elise) | $3,400.00 → $2,560.00 | 27,434 | resolved |
| 102 | Boss→Facilities, Facilities→Accounting | #2 $2,400.00 rent lease 1 (Elise) | $2,560.00 → $160.00 | 26,430 | resolved |
| 103 | Boss→Acct/Inv/CS, CS→Acct, CS→Inv | none | $160.00 (no change) | 51,807 | resolved |

The ending checking balance of **$160.00** matches `cash_accounts`. Details are in `output/desk_tickets.html` (Actual, Cash and Reflection tabs), `output/resolved_tickets.json` and `output/resolved_board.html`. Every step is in `output/audit_trail.json`.

---

## Shop rules → where each one is enforced

| Shop rule | Enforced by |
|---|---|
| `desk.date_today` is "today" | Every date calculation in the MCP server uses `_today()` from `desk`, and the dashboard shows the desk date |
| Lead times come from `vendors` | `check_vendor_can_ship` and `draft_vendor_reorder` use only `vendors.lead_days` |
| A vendor won't ship with an open unpaid invoice | `check_vendor_can_ship` returns `can_ship: false`; `draft_vendor_reorder` saves the draft as `blocked_unpaid_invoice` |
| Human approval for any payment; update the tables when paid | Agents only have `request_payment_approval`. `approve_and_pay` is human-only (hidden from agents, refuses agent names) and updates `cash_accounts`, `payments`, `invoices`/`leases`, `approvals` and `tickets` in one transaction |
| Not enough cash → the pay tool refuses | `approve_and_pay` refuses if amount > balance; `request_payment_approval` refuses if amount > balance |
| Cash only goes out | No revenue tool exists; `cash_accounts` only goes down |
| Reset before a full run | `POST /api/reset`, the dashboard's Reset button, or `python -m backend.run_team --reset` |
| Don't email customers or call vendors | No send tools exist. `draft_message` and `draft_vendor_reorder` only write to `drafts` |
| Only gpt-6-luna via Portkey | `MODEL_NAME` constant in `backend/config.py`; the audit trail logs the model each response reports |

---

## Agent prompts

Each prompt in `backend/prompts/` keeps its original one-sentence description as the opener and then covers role and scope, the shop rules that agent needs, how to route and delegate, and what to report. They were expanded after a first practice run with one-line prompts showed these problems:

- 103 fanned out to 5 hand-offs, with Customer Service re-delegating so Accounting and Inventory each ran twice.
- No customer replies were saved for 101 or 103.
- Facilities used the wrong `author` on a draft.

The final graded run (above) used the expanded prompts. The audit trail records each prompt file's hash on every `agent_started` event.

- **Boss:** routing by ticket type, one delegation at a time, Customer Service always last, re-check facts after humans act, status rules, and token discipline.
- **Inventory:** the vendor-block rule, `date_today + lead_days` arrivals only, reorders for only the quantity needed, and releasing held reorders after a payment.
- **Accounting:** check before filing, no duplicate requests, running totals, cost floor, and no invented discount policy.
- **Facilities:** lease from the database not the email, rent goes to Accounting, and `author="facilities"`.
- **Customer Service:** *drafts only, never sent*, always save a draft, no re-delegating, use released arrival dates, and no invented dates or discounts.

**Which runs in the audit trail are graded:** `audit_trail.json` is append-only, so it also holds earlier practice runs:
- the one-line-prompt runs `2eb5a59adce5`, `463ea7760cdc` and `51d56979ac88`;
- a later ticket-101 practice run, `8d5b4e0250a5`;
- a failed first attempt, `fa3cffa06d42`.

The **graded runs** are `4338ea3447e4`, `83c0dea08a19`, `e81e61963687`, `9b35ae8824f3`, `ce1db5469628` and `84a96fadf8fc`, all after the last `database_reset`. `data/campus_customs_new.db` in this repo is their end state: all 3 tickets resolved and checking at $160.00.
