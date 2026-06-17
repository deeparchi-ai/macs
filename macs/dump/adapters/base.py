"""Adapter base: wire normalized events into collector + trigger + sink.

A runtime adapter translates native telemetry into normalized events and calls
:meth:`DumpAdapter.feed`. On events that can complete a turn step
(``response`` / ``api_error`` / ``tool_post`` / ``approval``) it evaluates the
triggers and, on a hit, assembles + writes a dump. Everything is fail-open.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..collector import TurnCollector
from ..sinks import FileSink
from ..triggers import DEFAULT_TRIGGERS, evaluate

Key = Tuple[Optional[str], Optional[str]]

# Event kinds that should trigger evaluation (a turn step just completed).
_EVAL_ON = {"response", "api_error", "tool_post", "approval"}


class DumpAdapter:
    def __init__(self, collector: Optional[TurnCollector] = None,
                 sink: Optional[FileSink] = None,
                 triggers: Optional[List[Dict[str, Any]]] = None,
                 logger: Optional[Any] = None):
        self.collector = collector or TurnCollector()
        self.sink = sink or FileSink(logger=logger)
        self.triggers = triggers if triggers is not None else DEFAULT_TRIGGERS
        self.logger = logger

    def open_session(self, session_id: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self.collector.open(session_id, meta)

    def close_session(self, session_id: str) -> None:
        self.collector.evict(session_id)

    def feed(self, key: Key, kind: str, data: Dict[str, Any]) -> Optional[str]:
        """Record an event; if it completes a step and trips a trigger, dump.
        Returns the dump path when one is written, else ``None``. Fail-open."""
        try:
            self.collector.record(key, kind, data)
            if kind not in _EVAL_ON:
                return None
            hit = evaluate(self.triggers, self.collector.view(key), (kind, data))
            if hit is None:
                return None
            dump = self.collector.assemble(key, trigger=hit.to_dict())
            return self.sink.write(dump)
        except Exception as e:  # fail-open: never break the agent
            if self.logger is not None:
                try:
                    self.logger.warning(f"macs_dump: feed failed: {e!r}")
                except Exception:
                    pass
            return None
