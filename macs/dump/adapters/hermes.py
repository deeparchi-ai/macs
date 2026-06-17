"""Hermes adapter: map NousResearch/hermes-agent observer hooks -> MACS core.

Hooks contract (``hermes.observer.v1``): ``ctx.register_hook("<event>", cb)``,
callbacks take ``**kwargs``, fail-open, gated by ``has_hook``. We subscribe
read-only and never use middleware (dump is pure capture).

Confirmed payload fields used below come from the repo's
``docs/observability/README.md``. Anything provider-specific is read defensively
with ``.get`` so a payload change degrades gracefully rather than breaking.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .base import DumpAdapter
from ..collector import TurnCollector
from ..sinks import FileSink
from ..triggers import DEFAULT_TRIGGERS

Key = Tuple[Optional[str], Optional[str]]

_HOOKS = [
    "on_session_start", "on_session_end",
    "pre_api_request", "post_api_request", "api_request_error",
    "pre_tool_call", "post_tool_call",
    "subagent_start", "subagent_stop",
]


def _key(kw: Dict[str, Any]) -> Key:
    return (kw.get("session_id"), kw.get("turn_id"))


def _ms(seconds_or_ms: Any) -> Optional[float]:
    """Hermes reports api_duration; normalize to ms. Heuristic: < 1000 is sec."""
    if not isinstance(seconds_or_ms, (int, float)):
        return None
    return seconds_or_ms * 1000.0 if seconds_or_ms < 1000 else float(seconds_or_ms)


def build_adapter(ctx: Any) -> DumpAdapter:
    cfg = getattr(ctx, "config", {}) or {}
    get = cfg.get if hasattr(cfg, "get") else (lambda *a: None)
    logger = getattr(ctx, "logger", None)
    collector = TurnCollector(ttl_s=get("ttl_s") or 900.0,
                              maxlen=get("maxlen") or 200)
    sink = FileSink(base_dir=get("dir") or "~/.hermes/macs-dump", logger=logger)
    triggers = get("triggers") or DEFAULT_TRIGGERS
    return DumpAdapter(collector=collector, sink=sink, triggers=triggers, logger=logger)


def register(ctx: Any) -> DumpAdapter:
    """Hermes plugin entry point. Wires observer hooks to the dump adapter."""
    adapter = build_adapter(ctx)

    def on_session_start(**kw):
        adapter.open_session(kw.get("session_id"), {
            "model": kw.get("model"), "system_prompt": kw.get("system_prompt"),
            "platform": kw.get("source") or kw.get("platform"),
            "started_at": kw.get("started_at"),
            "parent_session_id": kw.get("parent_session_id"),
            "source_schema": kw.get("telemetry_schema_version", "hermes.observer.v1"),
        })

    def on_session_end(**kw):
        adapter.close_session(kw.get("session_id"))

    def pre_api_request(**kw):
        adapter.feed(_key(kw), "request", {
            "api_request_id": kw.get("api_request_id"),
            "model": kw.get("model"), "provider": kw.get("provider"),
            "system_prompt": kw.get("system_prompt"),
            "input_messages": kw.get("request"),
            "approx_input_tokens": kw.get("approx_input_tokens"),
            "started_at": kw.get("started_at"),
        })

    def post_api_request(**kw):
        adapter.feed(_key(kw), "response", {
            "api_request_id": kw.get("api_request_id"),
            "assistant_message": kw.get("assistant_message") or kw.get("response"),
            "finish_reason": kw.get("finish_reason"),
            "usage": kw.get("usage"),
            "duration_ms": _ms(kw.get("api_duration")),
            "model": kw.get("response_model"),
        })

    def api_request_error(**kw):
        adapter.feed(_key(kw), "api_error", {
            "status_code": kw.get("status_code"),
            "reason": kw.get("reason"),
            "retry_count": kw.get("retry_count"),
            "retryable": kw.get("retryable"),
            "error": kw.get("error"),
        })

    def pre_tool_call(**kw):
        adapter.feed(_key(kw), "tool_pre", {
            "tool_call_id": kw.get("tool_call_id"),
            "tool_name": kw.get("tool_name"), "args": kw.get("args"),
        })

    def post_tool_call(**kw):
        adapter.feed(_key(kw), "tool_post", {
            "tool_call_id": kw.get("tool_call_id"),
            "tool_name": kw.get("tool_name"), "status": kw.get("status"),
            "result": kw.get("result"), "duration_ms": kw.get("duration_ms"),
            "error_type": kw.get("error_type"),
            "error_message": kw.get("error_message"),
        })

    def subagent(**kw):
        adapter.feed(_key(kw), "subagent", {
            "subagent_id": kw.get("subagent_id"),
            "child_goal": kw.get("child_goal"),
            "child_summary": kw.get("child_summary"),
            "duration_ms": kw.get("duration_ms"),
        })

    handlers = {
        "on_session_start": on_session_start, "on_session_end": on_session_end,
        "pre_api_request": pre_api_request, "post_api_request": post_api_request,
        "api_request_error": api_request_error,
        "pre_tool_call": pre_tool_call, "post_tool_call": post_tool_call,
        "subagent_start": subagent, "subagent_stop": subagent,
    }
    for event, cb in handlers.items():
        try:
            ctx.register_hook(event, cb)
        except Exception:  # fail-open: a missing hook must not break load
            pass
    return adapter
