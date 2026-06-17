"""The ``macs.dump.v0`` artifact (runtime-agnostic).

A Decision-Chain Dump is a self-contained snapshot of one agent turn, keyed by
(session_id, turn_id) — the agent equivalent of a CICS Transaction DUMP. It is
the ownable interoperability contract of MACS; any runtime adapter produces the
same shape, so dumps are comparable across frameworks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "macs.dump.v0"
SOURCE_SCHEMA_DEFAULT = "hermes.observer.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_dump_id() -> str:
    return str(uuid.uuid4())


def build_dump(
    *,
    correlation: Dict[str, Any],
    context: Dict[str, Any],
    llm_response: Dict[str, Any],
    tool_calls: List[Dict[str, Any]],
    subagents: List[Dict[str, Any]],
    control_block: Dict[str, Any],
    env: Dict[str, Any],
    trigger: Dict[str, Any],
    source_schema: str = SOURCE_SCHEMA_DEFAULT,
    now_iso: Optional[str] = None,
    dump_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble a ``macs.dump.v0`` dict. ``now_iso``/``dump_id`` are injectable
    for deterministic tests."""
    return {
        "dump_id": dump_id or new_dump_id(),
        "schema": SCHEMA_VERSION,
        "source_telemetry_schema": source_schema,
        "captured_at": now_iso or utc_now_iso(),
        "trigger": trigger,
        "correlation": correlation,
        "context": context,
        "llm_response": llm_response,
        "tool_calls": tool_calls,
        "subagents": subagents,
        "control_block": control_block,
        "env": env,
    }


REQUIRED_KEYS = (
    "dump_id", "schema", "source_telemetry_schema", "captured_at", "trigger",
    "correlation", "context", "llm_response", "tool_calls", "subagents",
    "control_block", "env",
)
