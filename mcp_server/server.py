"""Campus Customs MCP server.

Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) reaches
the shop data through the tools defined here. All tools read from and write to
the working copy data/campus_customs_new.db; the original
data/campus_customs.db is never touched so the shop can be reset.

Tools only return what is actually stored in the database. If a row does not
exist, the tool says so instead of guessing. Amounts for payments are always
read from the database (invoice amount / lease rent), never taken from an agent.

Two support tables are created on startup if missing (a reset removes them,
which is what we want):
  - approvals: payment requests waiting for a human decision
  - drafts:    messages to customers / vendors / landlords. Drafts stay on the
               board; nothing is ever emailed or sent.

Human-only tools (approve_and_pay, reject_approval) are called by the backend's
approval endpoint on a person's behalf. The backend never exposes them to agents.
"""

import calendar
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB", "data/campus_customs_new.db"))
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_ROOT / DB_PATH  # .mcp.json uses project-relative paths

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}
PAYMENT_KINDS = {"invoice", "rent"}
RECIPIENT_TYPES = {"customer", "vendor", "landlord"}
DEFAULT_ACCOUNT = "checking"

mcp = FastMCP("campus-customs")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_support_tables(conn)
    return conn


def _ensure_support_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            ref_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payee TEXT NOT NULL,
            reason TEXT,
            requested_by TEXT NOT NULL,
            status TEXT NOT NULL,
            decided_by TEXT,
            decision_note TEXT,
            created_on TEXT NOT NULL,
            decided_on TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        );
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            recipient_type TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            author TEXT NOT NULL,
            status TEXT NOT NULL,
            created_on TEXT NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        );
        """
    )


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _today(conn: sqlite3.Connection) -> str:
    desk = _row(conn, "SELECT date_today FROM desk LIMIT 1")
    if desk is None:
        raise RuntimeError("desk.date_today is missing from the database.")
    return desk["date_today"]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _add_one_month(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def _append_ticket_note(conn: sqlite3.Connection, ticket_id: int, note: str) -> None:
    ticket = _row(conn, "SELECT notes FROM tickets WHERE id = ?", (ticket_id,))
    if ticket is None:
        return
    notes = ticket["notes"] or ""
    notes = f"{notes}\n{note}" if notes else note
    conn.execute("UPDATE tickets SET notes = ? WHERE id = ?", (notes, ticket_id))


def _open_invoices_for_vendor(conn: sqlite3.Connection, vendor_id: int) -> list[dict]:
    return _rows(
        conn,
        "SELECT * FROM invoices WHERE vendor_id = ? AND status != 'paid' ORDER BY due_date",
        (vendor_id,),
    )


def _is_agent_identity(name: str) -> bool:
    n = name.strip().lower().replace(" ", "_")
    return n in AGENT_NAMES or n in {"agent", "ai", "bot", "system", "assistant"}


# --------------------------------------------------------------------------- #
# Board / desk tools (all agents)
# --------------------------------------------------------------------------- #

@mcp.tool()
def get_shop_date() -> dict:
    """Return desk.date_today, the shop's "today". Use it (not the real clock)
    to decide what is overdue or due soon."""
    with _connect() as conn:
        return {"date_today": _today(conn)}


@mcp.tool()
def list_open_tickets() -> dict:
    """List every ticket on the board whose status is 'open', oldest first.

    Also returns desk.date_today, the shop's "today", so agents can judge
    what is overdue.
    """
    with _connect() as conn:
        tickets = _rows(
            conn,
            "SELECT * FROM tickets WHERE status = 'open' ORDER BY created_at, id",
        )
        return {"date_today": _today(conn), "count": len(tickets), "tickets": tickets}


@mcp.tool()
def list_tickets(status: str = "") -> dict:
    """List tickets on the board in any status (or only one status if given),
    so agents can see work that is in progress, blocked, or waiting approval."""
    with _connect() as conn:
        if status.strip():
            tickets = _rows(
                conn,
                "SELECT * FROM tickets WHERE status = ? ORDER BY created_at, id",
                (status.strip(),),
            )
        else:
            tickets = _rows(conn, "SELECT * FROM tickets ORDER BY created_at, id")
        return {"date_today": _today(conn), "count": len(tickets), "tickets": tickets}


@mcp.tool()
def get_ticket_details(ticket_id: int) -> dict:
    """Get one ticket plus every database row it links to.

    Depending on the ticket's fields this includes:
      - inventory rows for its sku (and the requested size, if any)
      - pricing for its sku
      - the linked invoice and that invoice's vendor
      - the linked lease
      - any approvals and drafts already filed for this ticket
    Only rows that exist in the database are returned. Nothing is inferred.
    """
    with _connect() as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"No ticket with id {ticket_id} exists."}

        linked: dict = {}

        if ticket["sku"]:
            linked["inventory"] = _rows(
                conn, "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (ticket["sku"],)
            )
            if ticket["size"]:
                linked["requested_size_stock"] = _row(
                    conn,
                    "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                    (ticket["sku"], ticket["size"]),
                )
            linked["pricing"] = _row(
                conn, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)
            )

        if ticket["invoice_id"] is not None:
            invoice = _row(
                conn, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
            )
            linked["invoice"] = invoice
            if invoice:
                linked["vendor"] = _row(
                    conn, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)
                )

        if ticket["lease_id"] is not None:
            linked["lease"] = _row(
                conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
            )

        approvals = _rows(conn, "SELECT * FROM approvals WHERE ticket_id = ?", (ticket_id,))
        drafts = _rows(conn, "SELECT * FROM drafts WHERE ticket_id = ?", (ticket_id,))
        if approvals:
            linked["approvals"] = approvals
        if drafts:
            linked["drafts"] = drafts

        return {"date_today": _today(conn), "ticket": ticket, "linked": linked}


@mcp.tool()
def update_ticket_status(ticket_id: int, status: str, note: str = "") -> dict:
    """Change a ticket's status (e.g. 'open', 'in_progress', 'waiting_approval',
    'resolved', 'blocked') and optionally append a note explaining why.

    The note is appended to the ticket's existing notes; earlier notes are kept.
    """
    status = status.strip()
    if not status:
        return {"error": "status must not be empty."}

    with _connect() as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"No ticket with id {ticket_id} exists."}

        notes = ticket["notes"] or ""
        if note.strip():
            notes = f"{notes}\n{note.strip()}" if notes else note.strip()

        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
            (status, notes, ticket_id),
        )
        updated = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))

    return {"previous_status": ticket["status"], "ticket": updated}


# --------------------------------------------------------------------------- #
# Inventory tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def check_stock(sku: str, size: str = "") -> dict:
    """Return on-hand inventory for a SKU (all sizes, or just one size)."""
    with _connect() as conn:
        if size.strip():
            rows = _rows(
                conn, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size.strip())
            )
        else:
            rows = _rows(conn, "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku,))
    if not rows:
        what = f"{sku} size {size}" if size.strip() else sku
        return {"error": f"No inventory rows for {what}."}
    return {"sku": sku, "rows": rows, "total_qty": sum(r["qty"] for r in rows)}


@mcp.tool()
def get_pricing(sku: str) -> dict:
    """Return unit_cost and list_price for a SKU."""
    with _connect() as conn:
        row = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
    if row is None:
        return {"error": f"No pricing row for {sku}."}
    return row


@mcp.tool()
def list_vendors() -> dict:
    """List every vendor with its specialty and lead_days (lead times come
    only from this table)."""
    with _connect() as conn:
        return {"vendors": _rows(conn, "SELECT * FROM vendors ORDER BY id")}


@mcp.tool()
def check_vendor_can_ship(vendor_id: int) -> dict:
    """Check whether a vendor will ship new product right now.

    Shop rule: a vendor will not ship while they still have an open unpaid
    invoice. Returns the vendor's open invoices (with days overdue vs.
    desk.date_today) and, if they can ship, the earliest arrival date
    (date_today + lead_days).
    """
    with _connect() as conn:
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            return {"error": f"No vendor with id {vendor_id} exists."}
        today = _today(conn)
        open_invoices = _open_invoices_for_vendor(conn, vendor_id)

    for inv in open_invoices:
        inv["days_overdue"] = max(0, _days_between(inv["due_date"], today))
    can_ship = not open_invoices
    result = {
        "date_today": today,
        "vendor": vendor,
        "can_ship": can_ship,
        "open_unpaid_invoices": open_invoices,
    }
    if can_ship:
        result["earliest_arrival_if_ordered_today"] = (
            date.fromisoformat(today) + timedelta(days=vendor["lead_days"])
        ).isoformat()
    else:
        result["reason"] = (
            f"{vendor['name']} has {len(open_invoices)} open unpaid invoice(s); "
            "they will not ship until paid."
        )
    return result


@mcp.tool()
def draft_vendor_reorder(
    ticket_id: int, vendor_id: int, sku: str, size: str, qty: int, author: str
) -> dict:
    """Write a DRAFT reorder to a vendor for a SKU/size. Nothing is sent.

    The draft is saved with status 'draft' if the vendor can ship, or
    'blocked_unpaid_invoice' if the vendor has an open unpaid invoice.
    """
    if qty <= 0:
        return {"error": "qty must be a positive number."}
    if author not in AGENT_NAMES:
        return {"error": f"author must be one of {sorted(AGENT_NAMES)}."}

    with _connect() as conn:
        if _row(conn, "SELECT id FROM tickets WHERE id = ?", (ticket_id,)) is None:
            return {"error": f"No ticket with id {ticket_id} exists."}
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            return {"error": f"No vendor with id {vendor_id} exists."}
        item = _row(
            conn, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        )
        if item is None:
            return {"error": f"No inventory row for {sku} size {size}; can't reorder an unknown item."}

        today = _today(conn)
        open_invoices = _open_invoices_for_vendor(conn, vendor_id)
        blocked = bool(open_invoices)
        status = "blocked_unpaid_invoice" if blocked else "draft"
        body = (
            f"Reorder request: {qty} x {item['name']} ({sku}) size {size}.\n"
            f"Requested on {today}. Vendor lead time: {vendor['lead_days']} days."
        )
        if blocked:
            ids = ", ".join(str(i["id"]) for i in open_invoices)
            body += f"\nHOLD: open unpaid invoice(s) {ids} must be paid before this can be sent."

        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient_type, recipient, subject, body, author, status, created_on) "
            "VALUES (?, 'vendor', ?, ?, ?, ?, ?, ?)",
            (ticket_id, vendor["name"], f"Reorder {sku} {size} x{qty}", body, author, status, today),
        )
        draft = _row(conn, "SELECT * FROM drafts WHERE id = ?", (cur.lastrowid,))

    result = {"draft": draft, "vendor_can_ship": not blocked}
    if not blocked:
        result["expected_arrival_if_sent_today"] = (
            date.fromisoformat(today) + timedelta(days=vendor["lead_days"])
        ).isoformat()
    return result


# --------------------------------------------------------------------------- #
# Accounting tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def get_cash_balance() -> dict:
    """Return the cash accounts and their balances, plus the total of payment
    requests still waiting for human approval. Cash only goes out; no revenue
    is modeled."""
    with _connect() as conn:
        accounts = _rows(conn, "SELECT * FROM cash_accounts ORDER BY name")
        pending = _row(
            conn,
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n FROM approvals WHERE status = 'pending'",
        )
    total = sum(a["balance"] for a in accounts)
    return {
        "accounts": accounts,
        "total_balance": total,
        "pending_approval_count": pending["n"],
        "pending_approval_total": pending["total"],
        "balance_if_all_pending_paid": total - pending["total"],
    }


@mcp.tool()
def list_invoices(status: str = "") -> dict:
    """List vendor invoices (optionally only one status, e.g. 'open'), with
    vendor name and days overdue vs. desk.date_today."""
    with _connect() as conn:
        today = _today(conn)
        sql = (
            "SELECT i.*, v.name AS vendor_name FROM invoices i "
            "JOIN vendors v ON v.id = i.vendor_id"
        )
        if status.strip():
            rows = _rows(conn, sql + " WHERE i.status = ? ORDER BY i.due_date", (status.strip(),))
        else:
            rows = _rows(conn, sql + " ORDER BY i.due_date")
    for r in rows:
        r["days_overdue"] = (
            max(0, _days_between(r["due_date"], today)) if r["status"] != "paid" else 0
        )
    return {"date_today": today, "invoices": rows}


@mcp.tool()
def list_payments() -> dict:
    """List every payment already made (the audit log of money out)."""
    with _connect() as conn:
        return {"payments": _rows(conn, "SELECT * FROM payments ORDER BY id")}


@mcp.tool()
def quote_bulk_price(sku: str, qty: int, discount_pct: float, size: str = "") -> dict:
    """Price a bulk / discounted order from the pricing table. Read-only.

    Returns the discounted unit price, total, margin per unit vs. unit_cost,
    whether the price stays above cost, and (if size is given) how many are
    in stock vs. requested. A price at or below cost is flagged not allowed.
    """
    if qty <= 0:
        return {"error": "qty must be a positive number."}
    if discount_pct < 0 or discount_pct >= 100:
        return {"error": "discount_pct must be between 0 and 100."}

    with _connect() as conn:
        price = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
        if price is None:
            return {"error": f"No pricing row for {sku}."}
        stock = (
            _row(conn, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size))
            if size.strip()
            else None
        )

    unit_price = round(price["list_price"] * (1 - discount_pct / 100), 2)
    margin = round(unit_price - price["unit_cost"], 2)
    result = {
        "sku": sku,
        "qty": qty,
        "discount_pct": discount_pct,
        "list_price": price["list_price"],
        "unit_cost": price["unit_cost"],
        "discounted_unit_price": unit_price,
        "total_price": round(unit_price * qty, 2),
        "margin_per_unit": margin,
        "total_margin": round(margin * qty, 2),
        "above_cost": margin > 0,
        "max_discount_pct_above_cost": round(
            (1 - price["unit_cost"] / price["list_price"]) * 100, 2
        ),
    }
    if not result["above_cost"]:
        result["allowed"] = False
        result["reason"] = "Discounted price is at or below unit_cost; the shop would lose money."
    else:
        result["allowed"] = True
    if size.strip():
        on_hand = stock["qty"] if stock else 0
        result["size"] = size
        result["in_stock"] = on_hand
        result["shortfall"] = max(0, qty - on_hand)
    return result


@mcp.tool()
def request_payment_approval(
    ticket_id: int, kind: str, ref_id: int, requested_by: str, reason: str
) -> dict:
    """Ask a human to approve a payment. This does NOT move money.

    kind is 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id).
    The amount and payee are read from the database, never supplied by the
    agent. The request is refused if the item is already paid, a request for
    it is already pending, or there is not enough cash to cover it. The
    ticket is set to 'waiting_approval'.
    """
    kind = kind.strip().lower()
    if kind not in PAYMENT_KINDS:
        return {"error": f"kind must be one of {sorted(PAYMENT_KINDS)}."}
    if requested_by not in AGENT_NAMES:
        return {"error": f"requested_by must be one of {sorted(AGENT_NAMES)}."}

    with _connect() as conn:
        if _row(conn, "SELECT id FROM tickets WHERE id = ?", (ticket_id,)) is None:
            return {"error": f"No ticket with id {ticket_id} exists."}
        today = _today(conn)

        if kind == "invoice":
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if inv is None:
                return {"error": f"No invoice with id {ref_id} exists."}
            if inv["status"] == "paid":
                return {"error": f"Invoice {ref_id} is already paid."}
            vendor = _row(conn, "SELECT name FROM vendors WHERE id = ?", (inv["vendor_id"],))
            amount, payee = inv["amount"], vendor["name"] if vendor else f"vendor {inv['vendor_id']}"
            what = f"invoice {ref_id} ({inv['description']}), due {inv['due_date']}"
        else:
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if lease is None:
                return {"error": f"No lease with id {ref_id} exists."}
            amount, payee = lease["monthly_rent"], lease["landlord"]
            what = f"rent for {lease['space_name']} due {lease['next_due']}"

        existing = _row(
            conn,
            "SELECT * FROM approvals WHERE kind = ? AND ref_id = ? AND status IN ('pending', 'approved')",
            (kind, ref_id),
        )
        if existing:
            return {"error": "A request for this payment is already waiting for a human.", "approval": existing}

        balance = _row(
            conn, "SELECT balance FROM cash_accounts WHERE name = ?", (DEFAULT_ACCOUNT,)
        )
        if balance is None:
            return {"error": f"No '{DEFAULT_ACCOUNT}' cash account exists."}
        pending_total = _row(
            conn, "SELECT COALESCE(SUM(amount), 0) AS t FROM approvals WHERE status = 'pending'"
        )["t"]
        if amount > balance["balance"]:
            return {
                "error": f"Not enough cash: {payee} needs ${amount:,.2f} but {DEFAULT_ACCOUNT} has ${balance['balance']:,.2f}.",
                "balance": balance["balance"],
            }

        cur = conn.execute(
            "INSERT INTO approvals (ticket_id, kind, ref_id, amount, payee, reason, requested_by, status, created_on) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, kind, ref_id, amount, payee, reason.strip(), requested_by, today),
        )
        conn.execute("UPDATE tickets SET status = 'waiting_approval' WHERE id = ?", (ticket_id,))
        _append_ticket_note(
            conn, ticket_id,
            f"[{today}] {requested_by}: requested human approval #{cur.lastrowid} to pay ${amount:,.2f} to {payee} for {what}.",
        )
        approval = _row(conn, "SELECT * FROM approvals WHERE id = ?", (cur.lastrowid,))

    result = {
        "approval": approval,
        "message": "Waiting for a human to approve. No money has moved.",
        "balance_now": balance["balance"],
        "balance_if_all_pending_paid": balance["balance"] - pending_total - amount,
    }
    if result["balance_if_all_pending_paid"] < 0:
        result["warning"] = "Approving every pending request would overdraw the account; a human must choose."
    return result


@mcp.tool()
def list_approvals(status: str = "", ticket_id: int = 0) -> dict:
    """List payment approval requests, optionally filtered by status
    ('pending', 'paid', 'rejected') and/or ticket."""
    sql, params, where = "SELECT * FROM approvals", [], []
    if status.strip():
        where.append("status = ?")
        params.append(status.strip())
    if ticket_id:
        where.append("ticket_id = ?")
        params.append(ticket_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with _connect() as conn:
        return {"approvals": _rows(conn, sql + " ORDER BY id", tuple(params))}


# --------------------------------------------------------------------------- #
# Facilities tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def get_lease(lease_id: int) -> dict:
    """Return one lease (space, landlord, monthly_rent, next_due) and how many
    days until rent is due vs. desk.date_today (negative = overdue)."""
    with _connect() as conn:
        lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
        if lease is None:
            return {"error": f"No lease with id {lease_id} exists."}
        today = _today(conn)
    lease["days_until_due"] = _days_between(today, lease["next_due"])
    return {"date_today": today, "lease": lease}


@mcp.tool()
def list_leases() -> dict:
    """List every lease with days until rent is due vs. desk.date_today."""
    with _connect() as conn:
        today = _today(conn)
        leases = _rows(conn, "SELECT * FROM leases ORDER BY next_due")
    for lease in leases:
        lease["days_until_due"] = _days_between(today, lease["next_due"])
    return {"date_today": today, "leases": leases}


# --------------------------------------------------------------------------- #
# Customer Service / messaging tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def draft_message(
    ticket_id: int, recipient_type: str, recipient: str, subject: str, body: str, author: str
) -> dict:
    """Save a DRAFT message to a customer, vendor, or landlord on the board.

    Nothing is emailed or sent. Drafts stay on the board for a human to review.
    recipient_type is 'customer', 'vendor', or 'landlord'.
    """
    recipient_type = recipient_type.strip().lower()
    if recipient_type not in RECIPIENT_TYPES:
        return {"error": f"recipient_type must be one of {sorted(RECIPIENT_TYPES)}."}
    if author not in AGENT_NAMES:
        return {"error": f"author must be one of {sorted(AGENT_NAMES)}."}
    if not subject.strip() or not body.strip():
        return {"error": "subject and body must not be empty."}

    with _connect() as conn:
        if _row(conn, "SELECT id FROM tickets WHERE id = ?", (ticket_id,)) is None:
            return {"error": f"No ticket with id {ticket_id} exists."}
        today = _today(conn)
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient_type, recipient, subject, body, author, status, created_on) "
            "VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)",
            (ticket_id, recipient_type, recipient.strip(), subject.strip(), body.strip(), author, today),
        )
        draft = _row(conn, "SELECT * FROM drafts WHERE id = ?", (cur.lastrowid,))
    return {"draft": draft, "message": "Saved as a draft on the board. Nothing was sent."}


@mcp.tool()
def list_drafts(ticket_id: int = 0) -> dict:
    """List draft messages on the board (all, or only for one ticket)."""
    with _connect() as conn:
        if ticket_id:
            rows = _rows(conn, "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        else:
            rows = _rows(conn, "SELECT * FROM drafts ORDER BY id")
    return {"drafts": rows}


# --------------------------------------------------------------------------- #
# Human-only tools (called by the backend approval endpoint, never by agents)
# --------------------------------------------------------------------------- #

@mcp.tool()
def approve_and_pay(approval_id: int, approved_by: str, account: str = DEFAULT_ACCOUNT) -> dict:
    """HUMAN ONLY. Approve a pending payment request and pay it.

    Refuses if approved_by is empty or an agent, if the request isn't
    pending, or if there is not enough cash (no negative balances). On
    success, in one transaction: deducts cash_accounts.balance, inserts a
    payments row, marks the invoice 'paid' or moves the lease's next_due
    forward one month, marks the approval 'paid', and notes the ticket.
    """
    approved_by = approved_by.strip()
    if not approved_by or _is_agent_identity(approved_by):
        return {"error": "approved_by must be the name of the human approving this payment."}

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        approval = _row(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if approval is None:
            return {"error": f"No approval with id {approval_id} exists."}
        if approval["status"] != "pending":
            return {"error": f"Approval {approval_id} is '{approval['status']}', not pending."}

        today = _today(conn)
        kind, ref_id = approval["kind"], approval["ref_id"]

        # Re-read the amount from the source row so a stale request can't overpay.
        if kind == "invoice":
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if inv is None or inv["status"] == "paid":
                return {"error": f"Invoice {ref_id} is missing or already paid."}
            amount = inv["amount"]
        else:
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if lease is None:
                return {"error": f"Lease {ref_id} is missing."}
            amount = lease["monthly_rent"]

        acct = _row(conn, "SELECT * FROM cash_accounts WHERE name = ?", (account,))
        if acct is None:
            return {"error": f"No cash account named '{account}'."}
        if amount > acct["balance"]:
            return {
                "error": f"REFUSED: not enough cash. Payment is ${amount:,.2f} but {account} has ${acct['balance']:,.2f}. No negative balances.",
                "approval": approval,
            }

        new_balance = round(acct["balance"] - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today, account),
        )
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account, today, approved_by),
        )
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            effect = f"invoice {ref_id} marked paid"
        else:
            next_due = _add_one_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, ref_id))
            effect = f"lease {ref_id} next_due moved {lease['next_due']} -> {next_due}"

        conn.execute(
            "UPDATE approvals SET status = 'paid', decided_by = ?, decided_on = ? WHERE id = ?",
            (approved_by, today, approval_id),
        )
        conn.execute(
            "UPDATE tickets SET status = 'in_progress' WHERE id = ? AND status = 'waiting_approval'",
            (approval["ticket_id"],),
        )
        _append_ticket_note(
            conn, approval["ticket_id"],
            f"[{today}] {approved_by} approved #{approval_id}: paid ${amount:,.2f} to {approval['payee']} "
            f"from {account} (payment #{cur.lastrowid}); {effect}.",
        )
        payment = _row(conn, "SELECT * FROM payments WHERE id = ?", (cur.lastrowid,))
        approval = _row(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))

    return {"payment": payment, "approval": approval, "new_balance": new_balance, "effect": effect}


@mcp.tool()
def reject_approval(approval_id: int, decided_by: str, reason: str = "") -> dict:
    """HUMAN ONLY. Reject a pending payment request. No money moves."""
    decided_by = decided_by.strip()
    if not decided_by or _is_agent_identity(decided_by):
        return {"error": "decided_by must be the name of the human rejecting this payment."}

    with _connect() as conn:
        approval = _row(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if approval is None:
            return {"error": f"No approval with id {approval_id} exists."}
        if approval["status"] != "pending":
            return {"error": f"Approval {approval_id} is '{approval['status']}', not pending."}
        today = _today(conn)
        conn.execute(
            "UPDATE approvals SET status = 'rejected', decided_by = ?, decision_note = ?, decided_on = ? WHERE id = ?",
            (decided_by, reason.strip(), today, approval_id),
        )
        conn.execute(
            "UPDATE tickets SET status = 'blocked' WHERE id = ? AND status = 'waiting_approval'",
            (approval["ticket_id"],),
        )
        _append_ticket_note(
            conn, approval["ticket_id"],
            f"[{today}] {decided_by} rejected payment request #{approval_id}"
            + (f": {reason.strip()}" if reason.strip() else "."),
        )
        approval = _row(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
    return {"approval": approval}


if __name__ == "__main__":
    mcp.run(show_banner=False)
