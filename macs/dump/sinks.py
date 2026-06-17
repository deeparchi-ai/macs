"""Where dumps go. v0 is file-based (the SMF/RMF "just write it" analog).

All writes are **fail-open**: a sink error must never propagate into the agent.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class FileSink:
    """Write each dump as a JSON file under ``base_dir/<date>/`` and append a
    one-line summary to ``index.jsonl`` for cheap retrieval."""

    def __init__(self, base_dir: str = "~/.hermes/macs-dump",
                 logger: Optional[Any] = None):
        self.base_dir = os.path.expanduser(base_dir)
        self.logger = logger

    def _log(self, msg: str) -> None:
        if self.logger is not None:
            try:
                self.logger.warning(msg)
            except Exception:
                pass

    def write(self, dump: Dict[str, Any]) -> Optional[str]:
        try:
            captured = dump.get("captured_at", "")
            date = captured[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            day_dir = os.path.join(self.base_dir, date)
            os.makedirs(day_dir, exist_ok=True)

            corr = dump.get("correlation", {})
            sid = str(corr.get("session_id") or "nosession")[:24]
            tid = str(corr.get("turn_id") or "noturn")[:24]
            did = dump.get("dump_id", "dump")
            path = os.path.join(day_dir, f"{sid}__{tid}__{did}.json")

            with open(path, "w", encoding="utf-8") as f:
                json.dump(dump, f, ensure_ascii=False, indent=2)

            self._append_index(day_dir, dump, path)
            return path
        except Exception as e:  # fail-open
            self._log(f"macs_dump: sink write failed: {e!r}")
            return None

    def _append_index(self, day_dir: str, dump: Dict[str, Any], path: str) -> None:
        try:
            line = {
                "dump_id": dump.get("dump_id"),
                "captured_at": dump.get("captured_at"),
                "trigger": dump.get("trigger", {}).get("predicate"),
                "session_id": dump.get("correlation", {}).get("session_id"),
                "turn_id": dump.get("correlation", {}).get("turn_id"),
                "path": path,
            }
            with open(os.path.join(day_dir, "index.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception as e:  # fail-open
            self._log(f"macs_dump: index append failed: {e!r}")
