"""Per-turn ring buffer that assembles a Decision-Chain Dump on trigger.

Observer hooks are an always-on telemetry stream (like SMF/RMF "on by default").
The collector keeps a bounded, TTL'd in-memory buffer per (session_id, turn_id);
when a trigger fires it freezes the whole chain into a ``macs.dump.v0`` artifact
(like SLIP -> Transaction DUMP), then the buffer is evicted on session end.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

from .model import build_dump

Key = Tuple[Optional[str], Optional[str]]
Event = Tuple[str, Dict[str, Any]]


@dataclass
class TurnBuffer:
    session_id: Optional[str]
    turn_id: Optional[str]
    events: Deque[Event]
    created_at: float
    session_meta: Dict[str, Any] = field(default_factory=dict)


class TurnCollector:
    def __init__(self, ttl_s: float = 900.0, maxlen: int = 200):
        self.ttl_s = ttl_s
        self.maxlen = maxlen
        self._buffers: Dict[Key, TurnBuffer] = {}
        self._session_meta: Dict[str, Dict[str, Any]] = {}

    # --- lifecycle ----------------------------------------------------------
    def open(self, session_id: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._session_meta[session_id] = meta or {}

    def evict(self, session_id: str) -> None:
        for k in [k for k in self._buffers if k[0] == session_id]:
            self._buffers.pop(k, None)
        self._session_meta.pop(session_id, None)

    def _gc(self, now: float) -> None:
        dead = [k for k, b in self._buffers.items() if now - b.created_at > self.ttl_s]
        for k in dead:
            self._buffers.pop(k, None)

    # --- recording ----------------------------------------------------------
    def record(self, key: Key, kind: str, data: Dict[str, Any],
               now: Optional[float] = None) -> TurnBuffer:
        now = time.time() if now is None else now
        self._gc(now)
        b = self._buffers.get(key)
        if b is None:
            b = TurnBuffer(
                session_id=key[0], turn_id=key[1],
                events=deque(maxlen=self.maxlen), created_at=now,
                session_meta=self._session_meta.get(key[0], {}),
            )
            self._buffers[key] = b
        b.events.append((kind, dict(data)))
        return b

    def view(self, key: Key) -> List[Event]:
        b = self._buffers.get(key)
        return list(b.events) if b else []

    # --- assembly -----------------------------------------------------------
    def assemble(self, key: Key, trigger: Dict[str, Any],
                 now_iso: Optional[str] = None,
                 dump_id: Optional[str] = None) -> Dict[str, Any]:
        b = self._buffers.get(key)
        events: List[Event] = list(b.events) if b else []
        meta = b.session_meta if b else {}

        req = next((d for k, d in events if k == "request"), {})
        resp = next((d for k, d in reversed(events) if k == "response"), {})
        api_errors = [d for k, d in events if k == "api_error"]

        tool_pre = {d.get("tool_call_id"): d for k, d in events if k == "tool_pre"}
        tool_calls: List[Dict[str, Any]] = []
        for k, d in events:
            if k != "tool_post":
                continue
            pre = tool_pre.get(d.get("tool_call_id"), {})
            tool_calls.append({
                "tool_call_id": d.get("tool_call_id"),
                "tool_name": d.get("tool_name") or pre.get("tool_name"),
                "args": pre.get("args"),
                "status": d.get("status"),
                "duration_ms": d.get("duration_ms"),
                "result": d.get("result"),
                "error_type": d.get("error_type"),
                "error_message": d.get("error_message"),
            })

        subagents = [d for k, d in events if k == "subagent"]

        correlation = {
            "session_id": key[0],
            "turn_id": key[1],
            "api_request_id": resp.get("api_request_id") or req.get("api_request_id"),
            "parent_session_id": meta.get("parent_session_id"),
            "subagent_id": meta.get("subagent_id"),
        }
        context = {
            "model": req.get("model") or resp.get("model") or meta.get("model"),
            "provider": req.get("provider"),
            "system_prompt": req.get("system_prompt") or meta.get("system_prompt"),
            "input_messages": req.get("input_messages"),
            "approx_input_tokens": req.get("approx_input_tokens"),
        }
        llm_response = {
            "assistant_message": resp.get("assistant_message"),
            "finish_reason": resp.get("finish_reason"),
            "usage": resp.get("usage"),
            "reasoning": resp.get("reasoning"),
        }
        control_block = {
            "started_at": req.get("started_at") or meta.get("started_at"),
            "api_call_count": sum(1 for k, _ in events if k == "request"),
            "tool_call_count": len(tool_calls),
            "retry_count": max((d.get("retry_count") or 0 for d in api_errors), default=0),
            "duration_ms": resp.get("duration_ms"),
            "tokens": (resp.get("usage") or {}),
            "estimated_cost_usd": resp.get("estimated_cost_usd"),
        }
        env = {
            "hermes_version": meta.get("hermes_version"),
            "platform": meta.get("platform") or req.get("provider"),
            "cwd": meta.get("cwd"),
        }

        return build_dump(
            correlation=correlation, context=context, llm_response=llm_response,
            tool_calls=tool_calls, subagents=subagents, control_block=control_block,
            env=env, trigger=trigger,
            source_schema=meta.get("source_schema", "hermes.observer.v1"),
            now_iso=now_iso, dump_id=dump_id,
        )
