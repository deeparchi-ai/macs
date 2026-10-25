"""Where dumps go. v0 is file-based (the SMF/RMF "just write it" analog).

All writes are **fail-open**: a sink error must never propagate into the agent.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


def _json_fallback(o: Any) -> Any:
    """Last-resort serializer — never raise, so a dump is never half-written.

    Observer payloads sometimes carry live Python objects (dataclasses, sets,
    bytes, provider SDK response objects). Without this, ``json.dump`` raises
    *mid-stream* and leaves a truncated .json on disk that can never be parsed
    (observed 2026-10-24: one 622 KB dump cut at ``llm_response.assistant_message``).
    """
    try:
        if isinstance(o, (set, frozenset)):
            return sorted(str(x) for x in o)
        if isinstance(o, (bytes, bytearray)):
            return o.decode("utf-8", "replace")
        if hasattr(o, "_asdict"):          # namedtuple
            return dict(o._asdict())
        if hasattr(o, "__dict__"):         # dataclass / SDK object
            return {k: v for k, v in vars(o).items() if not k.startswith("_")}
        if isinstance(o, BaseException):
            return f"{type(o).__name__}: {o}"
    except Exception:                       # noqa: BLE001 - fallback must never raise
        pass
    return repr(o)[:2000]


class FileSink:
    """Write each dump as a JSON file under ``base_dir/<date>/`` and append a
    one-line summary to ``index.jsonl`` for cheap retrieval.

    Writes are ATOMIC: serialize fully in memory, write to ``.tmp``, fsync,
    then ``os.replace``. A process killed mid-write therefore leaves either no
    file or a complete one — never a truncated .json that silently poisons the
    daily parse-rate. (Kept in lockstep with the installed plugin at
    ``~/.hermes/plugins/observability/macs_dump/__init__.py``.)
    """

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
            # Bucket by LOCAL date: captured_at is UTC, so slicing it put evening
            # (CST) dumps into the previous day's folder and split daily reports.
            date = datetime.now().strftime("%Y-%m-%d")
            day_dir = os.path.join(self.base_dir, date)
            os.makedirs(day_dir, exist_ok=True)

            corr = dump.get("correlation", {})
            sid = str(corr.get("session_id") or "nosession")[:24]
            tid = str(corr.get("turn_id") or "noturn")[:24]
            did = dump.get("dump_id", "dump")
            path = os.path.join(day_dir, f"{sid}__{tid}__{did}.json")

            # Serialize fully in memory first: a write must never leave a half file.
            payload = json.dumps(dump, ensure_ascii=False, indent=2,
                                 default=_json_fallback)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)

            self._append_index(day_dir, dump, path)
            return path
        except Exception as e:  # fail-open
            self._log(f"macs_dump: sink write failed: {e!r}")
            self._tombstone(dump, e)
            return None

    def _tombstone(self, dump: Dict[str, Any], err: Exception) -> None:
        """Leave an honest marker instead of silence: a lost dump must be visible."""
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            day_dir = os.path.join(self.base_dir, date)
            os.makedirs(day_dir, exist_ok=True)
            p = os.path.join(day_dir, f"FAILED__{dump.get('dump_id', 'unknown')}.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"dump_id": dump.get("dump_id"),
                           "captured_at": dump.get("captured_at"),
                           "write_error": repr(err),
                           "trigger": dump.get("trigger")},
                          f, ensure_ascii=False, indent=2, default=_json_fallback)
        except Exception:  # noqa: BLE001
            pass

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
