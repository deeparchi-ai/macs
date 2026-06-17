"""Hermes adapter: map NousResearch/hermes-agent observer hooks -> MACS core.

Plugin contract (verified against installed **v0.16.0**, commit 5d3be89):
  - entry point ``def register(ctx)``; ``ctx.register_hook("<event>", cb)``;
    callbacks are keyword-only and must accept ``**_`` for forward-compat.
  - ``PluginContext`` has no ``.config``/``.logger`` attribute — read defensively.

Events actually emitted by v0.16.0 (``invoke_hook``):
    pre_api_request, post_api_request, pre_llm_call, post_llm_call,
    pre_tool_call, post_tool_call, on_session_finalize
Correlation is ``(session_id, task_id)`` + ``api_call_count`` — there is **no
turn_id**. Tool failure has **no status field**; it is encoded inside ``result``
(a dict carrying a truthy ``error``). ``api_duration`` is in **seconds**.

GitHub-main names (turn_id, api_request_error, subagent_*, status/duration on
tool calls) are read as fallbacks so the same adapter also works on newer Hermes.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .base import DumpAdapter
from ..collector import TurnCollector
from ..sinks import FileSink
from ..triggers import DEFAULT_TRIGGERS

Key = Tuple[Optional[str], Optional[str]]


def _key(kw: Dict[str, Any]) -> Key:
    # v0.16.0 keys on task_id; newer builds may carry turn_id.
    return (kw.get("session_id"), kw.get("task_id") or kw.get("turn_id"))


def _ms(value: Any) -> Optional[float]:
    """Hermes reports api_duration in seconds; normalize to ms. (Heuristic
    keeps already-ms values from older/other builds intact.)"""
    if not isinstance(value, (int, float)):
        return None
    return value * 1000.0 if value < 1000 else float(value)


def _tool_status(result: Any) -> Tuple[str, Optional[str]]:
    """Derive ok/error from a tool result (v0.16.0 has no status field)."""
    if isinstance(result, dict):
        err = result.get("error") or result.get("is_error") or result.get("isError")
        if err:
            return "error", str(result.get("error") or result.get("error_message") or err)
    if isinstance(result, str) and result.strip().lower().startswith("error"):
        return "error", result[:300]
    return "ok", None


def build_adapter(ctx: Any) -> DumpAdapter:
    cfg = getattr(ctx, "config", None) or {}
    get = cfg.get if hasattr(cfg, "get") else (lambda *a: None)
    logger = getattr(ctx, "logger", None)
    collector = TurnCollector(ttl_s=get("ttl_s") or 900.0, maxlen=get("maxlen") or 200)
    sink = FileSink(base_dir=get("dir") or "~/.hermes/macs-dump", logger=logger)
    triggers = get("triggers") or DEFAULT_TRIGGERS
    return DumpAdapter(collector=collector, sink=sink, triggers=triggers, logger=logger)


def register(ctx: Any) -> DumpAdapter:
    """Hermes plugin entry point. Wires observer hooks to the dump adapter."""
    adapter = build_adapter(ctx)

    def pre_api_request(**kw):
        adapter.collector.open(kw.get("session_id"), {
            "model": kw.get("model"), "platform": kw.get("platform"),
            "source_schema": "hermes.observer.v1",
        })
        adapter.feed(_key(kw), "request", {
            "api_request_id": str(kw.get("api_call_count", "")),
            "model": kw.get("model"), "provider": kw.get("provider"),
            "system_prompt": kw.get("system_prompt"),
            "input_messages": kw.get("request_messages") or kw.get("messages")
                              or kw.get("conversation_history") or kw.get("request"),
            "approx_input_tokens": kw.get("approx_input_tokens"),
            "started_at": kw.get("started_at"),
        })

    def post_api_request(**kw):
        adapter.feed(_key(kw), "response", {
            "api_request_id": str(kw.get("api_call_count", "")),
            "assistant_message": kw.get("assistant_message") or kw.get("response")
                                 or kw.get("assistant_response"),
            "finish_reason": kw.get("finish_reason"),
            "usage": kw.get("usage"),
            "duration_ms": _ms(kw.get("api_duration") or kw.get("duration_ms")),
            "model": kw.get("model"),
        })

    def pre_tool_call(**kw):
        adapter.feed(_key(kw), "tool_pre", {
            "tool_call_id": kw.get("tool_call_id"),
            "tool_name": kw.get("tool_name"), "args": kw.get("args"),
        })

    def post_tool_call(**kw):
        result = kw.get("result")
        status = kw.get("status")
        err_msg = kw.get("error_message")
        if status is None:  # v0.16.0: derive from result
            status, err_msg = _tool_status(result)
        adapter.feed(_key(kw), "tool_post", {
            "tool_call_id": kw.get("tool_call_id"),
            "tool_name": kw.get("tool_name"), "args": kw.get("args"),
            "status": status, "result": result,
            "duration_ms": kw.get("duration_ms"),
            "error_type": kw.get("error_type"), "error_message": err_msg,
        })

    def api_request_error(**kw):  # newer Hermes only; harmless if never fired
        adapter.feed(_key(kw), "api_error", {
            "status_code": kw.get("status_code"), "reason": kw.get("reason"),
            "retry_count": kw.get("retry_count"), "error": kw.get("error"),
        })

    def subagent(**kw):  # newer Hermes only
        adapter.feed(_key(kw), "subagent", {
            "subagent_id": kw.get("subagent_id"), "child_goal": kw.get("child_goal"),
            "child_summary": kw.get("child_summary"), "duration_ms": kw.get("duration_ms"),
        })

    def on_session_finalize(**kw):
        adapter.close_session(kw.get("session_id"))

    handlers = {
        "pre_api_request": pre_api_request,
        "post_api_request": post_api_request,
        "pre_tool_call": pre_tool_call,
        "post_tool_call": post_tool_call,
        "on_session_finalize": on_session_finalize,
        # forward-compat (not emitted by v0.16.0; registering is harmless):
        "api_request_error": api_request_error,
        "subagent_start": subagent,
        "subagent_stop": subagent,
    }
    for event, cb in handlers.items():
        try:
            ctx.register_hook(event, cb)
        except Exception:  # fail-open: a missing/unknown hook must not break load
            pass
    return adapter
