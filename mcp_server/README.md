# Campus Customs MCP Server

## What it's for
This is the shared toolbox for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents don't query the database themselves. Every read and write goes through these MCP tools, so all agents see the same data. Tools only return what is stored in the database and give an error if a row doesn't exist. They never make up data.

Built with [FastMCP](https://github.com/jlowin/fastmcp).

## Database
- **Uses:** `data/campus_customs_new.db` (the working copy; tools update it as tickets are resolved)
- **Never touches:** `data/campus_customs.db` (the original). To reset, copy it over the working copy:
  ```bash
  cp data/campus_customs.db data/campus_customs_new.db
  ```
- You can point the server at a different file with the `CAMPUS_CUSTOMS_DB` environment variable.

## Tools
Payments are a two-step process. Agents *request* approval, and only a human can *approve and pay*. The human-only tools are hidden from every agent and are called by the backend's approval endpoint.

| Area | Tool | What it does |
|---|---|---|
| Board | `get_shop_date()` | `desk.date_today`, the shop's "today." |
| Board | `list_open_tickets()` | Open tickets (oldest first) + `date_today`. |
| Board | `list_tickets(status="")` | Tickets in any status (or one status). |
| Board | `get_ticket_details(ticket_id)` | One ticket + its linked inventory, pricing, invoice, vendor, lease, approvals, drafts. |
| Board | `update_ticket_status(ticket_id, status, note="")` | Change status and append a note. |
| Inventory | `check_stock(sku, size="")` | On-hand qty for a SKU (one size or all). |
| Inventory | `get_pricing(sku)` | `unit_cost` and `list_price`. |
| Inventory | `list_vendors()` | Vendors with specialty and `lead_days`. |
| Inventory | `check_vendor_can_ship(vendor_id)` | Open unpaid invoices block shipping; otherwise earliest arrival = today + lead days. |
| Inventory | `draft_vendor_reorder(ticket_id, vendor_id, sku, size, qty, author)` | Saves a reorder **draft** (held if the vendor has unpaid invoices). Nothing is sent. |
| Inventory | `release_held_reorders(vendor_id)` | Re-checks a vendor; once all its invoices are paid, flips held reorder drafts to ready-to-send with the expected arrival date. Nothing is sent. |
| Accounting | `get_cash_balance()` | Balances + total of pending approval requests. |
| Accounting | `list_invoices(status="")` | Invoices with vendor name and days overdue. |
| Accounting | `list_payments()` | Every payment made. |
| Accounting | `quote_bulk_price(sku, qty, discount_pct, size="")` | Discounted price, margin vs. cost, stock shortfall; below-cost prices are flagged not allowed. |
| Accounting | `request_payment_approval(ticket_id, kind, ref_id, requested_by, reason)` | Files a payment request for a human (amount read from the DB). No money moves. |
| Accounting | `list_approvals(status="", ticket_id=0)` | Payment requests and their status. |
| Facilities | `get_lease(lease_id)` | Lease + days until rent is due. |
| Facilities | `list_leases()` | All leases + days until due. |
| Messaging | `draft_message(ticket_id, recipient_type, recipient, subject, body, author)` | Saves a customer/vendor/landlord **draft** on the board. Nothing is sent. |
| Messaging | `list_drafts(ticket_id=0)` | Drafts on the board. |
| Human only | `approve_and_pay(approval_id, approved_by, account="checking")` | Pays a pending request: refuses agents as approvers and refuses if cash would go negative. Updates `cash_accounts`, `payments`, and `invoices`/`leases`, `approvals`, `tickets`, and auto-releases that vendor's held reorder drafts once its last invoice is paid. |
| Human only | `reject_approval(approval_id, decided_by, reason="")` | Rejects a pending request. No money moves. |

The server also creates two support tables if they're missing: `approvals` (payment requests) and `drafts` (messages on the board).

## Running
```bash
pip install -r mcp_server/requirements.txt
python mcp_server/server.py
```

## Connecting and testing
The project's `.mcp.json` registers this server as `campus-customs` (stdio, using `.venv/bin/python`). To check all three tools against the database:
```bash
.venv/bin/python mcp_server/smoke_test.py
```
This writes the evidence to `output/mcp_smoke.json`.
