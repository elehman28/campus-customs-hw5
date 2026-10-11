"""Append-only audit trail: output/audit_trail.json.

The file is a JSON array. Every event is appended; the file is never wiped
between runs. Each agent loop step (prompt in, model request, model response
with tool calls, final output) becomes one event, so a run can be replayed
and checked later.
"""

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config import AUDIT_MAX_CHARS, AUDIT_PATH

_lock = threading.Lock()

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _redact(text: str) -> str:
    text = _EMAIL_RE.sub("[email redacted]", text)
    return _CARD_RE.sub("[number redacted]", text)


def clean(value: Any) -> Any:
    """Make a value JSON-safe, redact emails / card-like numbers, and cap long strings."""
    if isinstance(value, str):
        value = _redact(value)
        if len(value) > AUDIT_MAX_CHARS:
            value = value[:AUDIT_MAX_CHARS] + f"... [truncated {len(value) - AUDIT_MAX_CHARS} chars]"
        return value
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return clean(value.model_dump(mode="json"))
    return clean(str(value))


def append_event(event_type: str, **fields: Any) -> dict:
    """Append one event to output/audit_trail.json and return it."""
    event = {
        "event_id": uuid.uuid4().hex[:12],
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event_type,
        **clean(fields),
    }
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        events: list = []
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
            events = json.loads(AUDIT_PATH.read_text())
        events.append(event)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(events, indent=2) + "\n")
        os.replace(tmp, AUDIT_PATH)  # atomic: a crash mid-write never corrupts the trail
    return event


def read_events() -> list[dict]:
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    return json.loads(AUDIT_PATH.read_text())
