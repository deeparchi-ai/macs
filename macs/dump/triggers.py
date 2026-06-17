"""SLIP-style trigger engine (runtime-agnostic).

A *trigger* is a small dict ``{"predicate": name, ...params}``. Predicates are
evaluated against the normalized event stream of a single turn. The first
matching trigger wins and yields a :class:`TriggerHit` — the agent equivalent of
a z/OS SLIP trap firing a DUMP.

Normalized events are ``(kind, data)`` tuples, ``kind`` in:
    request | response | api_error | tool_pre | tool_post | subagent | approval
The runtime adapter is responsible for producing these from its own hooks and
for normalizing units (e.g. durations into ``duration_ms``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

Event = Tuple[str, Dict[str, Any]]


@dataclass
class TriggerHit:
    predicate: str
    detail: str = ""
    matched_value: Any = None
    threshold: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predicate": self.predicate,
            "detail": self.detail,
            "matched_value": self.matched_value,
            "threshold": self.threshold,
        }


# --- predicates: (params, events, latest) -> Optional[TriggerHit] ------------

def _tool_error(params, events, latest):
    kind, data = latest
    if kind == "tool_post" and data.get("status") == "error":
        return TriggerHit("tool_error", detail=f"tool={data.get('tool_name')}",
                          matched_value=data.get("error_type") or data.get("error_message"))
    return None


def _tool_repeat_fail(params, events, latest):
    kind, data = latest
    if kind != "tool_post" or data.get("status") != "error":
        return None
    threshold = int(params.get("threshold", 3))
    name = data.get("tool_name")
    count = sum(1 for k, d in events
                if k == "tool_post" and d.get("tool_name") == name and d.get("status") == "error")
    if count >= threshold:
        return TriggerHit("tool_repeat_fail", detail=f"tool={name}",
                          matched_value=count, threshold=threshold)
    return None


def _api_error(params, events, latest):
    kind, data = latest
    if kind == "api_error":
        return TriggerHit("api_error",
                          detail=str(data.get("reason") or data.get("status_code") or ""),
                          matched_value=data.get("status_code"))
    return None


def _latency(params, events, latest):
    kind, data = latest
    threshold = int(params.get("threshold_ms", 30000))
    dur = data.get("duration_ms")
    if kind == "response" and isinstance(dur, (int, float)) and dur > threshold:
        return TriggerHit("latency", detail="api_duration",
                          matched_value=dur, threshold=threshold)
    return None


def _finish_anomaly(params, events, latest):
    kind, data = latest
    reasons = set(params.get("reasons", ["length", "content_filter"]))
    if kind == "response" and data.get("finish_reason") in reasons:
        return TriggerHit("finish_anomaly", matched_value=data.get("finish_reason"))
    return None


def _approval_denied(params, events, latest):
    kind, data = latest
    if kind == "approval" and data.get("approved") is False:
        return TriggerHit("approval_denied", detail=str(data.get("tool_name", "")))
    return None


PREDICATES: Dict[str, Callable[..., Optional[TriggerHit]]] = {
    "tool_error": _tool_error,
    "tool_repeat_fail": _tool_repeat_fail,
    "api_error": _api_error,
    "latency": _latency,
    "finish_anomaly": _finish_anomaly,
    "approval_denied": _approval_denied,
}

# Sensible defaults — SMF/RMF "on by default", SLIP-style escalation.
DEFAULT_TRIGGERS: List[Dict[str, Any]] = [
    {"predicate": "tool_repeat_fail", "threshold": 3},
    {"predicate": "api_error"},
    {"predicate": "latency", "threshold_ms": 30000},
    {"predicate": "finish_anomaly", "reasons": ["length", "content_filter"]},
    {"predicate": "approval_denied"},
]


def evaluate(triggers: List[Dict[str, Any]], events: List[Event],
             latest: Event) -> Optional[TriggerHit]:
    """Return the first :class:`TriggerHit`, or ``None`` if nothing fired."""
    for t in triggers:
        fn = PREDICATES.get(t.get("predicate"))
        if fn is None:
            continue
        hit = fn(t, events, latest)
        if hit is not None:
            return hit
    return None
