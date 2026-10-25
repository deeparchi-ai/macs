"""FileSink must be ATOMIC — a killed process may never leave a truncated dump.

Regression guard for the 2026-10-24 incident: one 622 KB dump was cut mid-write
at ``llm_response.assistant_message`` (non-atomic ``open()+json.dump``), which
silently dropped the day's parse rate to 97.3% and cost one whole session's
telemetry.
"""
import json
import os

import _bootstrap  # noqa: F401

from macs.dump.sinks import FileSink


def _dump(**over):
    d = {
        "dump_id": "d-1",
        "captured_at": "2026-10-24T01:25:01.155353+00:00",
        "schema": "macs.dump.v0",
        "correlation": {"session_id": "s-1", "turn_id": "t-1"},
        "trigger": {"predicate": "latency"},
        "inputs": {"messages": [{"role": "user", "content": "hi"}]},
        "llm_response": {"assistant_message": "hello"},
    }
    d.update(over)
    return d


def _jsons(root):
    return [os.path.join(r, n) for r, _d, ns in os.walk(root) for n in ns if n.endswith(".json")]


def test_write_is_parseable_and_indexed(tmp_path):
    sink = FileSink(base_dir=str(tmp_path))
    path = sink.write(_dump())
    assert path and os.path.exists(path)
    json.load(open(path, encoding="utf-8"))          # parses
    idx = os.path.join(os.path.dirname(path), "index.jsonl")
    assert os.path.exists(idx) and len(open(idx, encoding="utf-8").read().strip().splitlines()) == 1
    assert not [p for p in _jsons(str(tmp_path)) if p.endswith(".tmp")], "tmp file left behind"


def test_unserializable_payload_never_truncates(tmp_path):
    """set/bytes/arbitrary objects must be coerced, not raise mid-stream."""
    class Opaque:
        def __init__(self):
            self.a = 1

    sink = FileSink(base_dir=str(tmp_path))
    path = sink.write(_dump(llm_response={"assistant_message": {"tags": {"x", "y"},
                                                               "raw": b"\x00\x01",
                                                               "sdk": Opaque()}}))
    assert path, "write must not fail on unserializable payloads"
    data = json.load(open(path, encoding="utf-8"))   # full document, parses
    am = data["llm_response"]["assistant_message"]
    assert sorted(am["tags"]) == ["x", "y"] and am["raw"] == "\x00\x01" and am["sdk"] == {"a": 1}


def test_no_partial_file_when_replace_fails(tmp_path, monkeypatch):
    """If the atomic replace fails, the target must be ABSENT (not half-written),
    and a FAILED__ tombstone must make the loss visible."""
    sink = FileSink(base_dir=str(tmp_path))

    def boom(*_a, **_kw):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(os, "replace", boom)
    assert sink.write(_dump()) is None                # fail-open: no raise

    files = [os.path.basename(p) for p in _jsons(str(tmp_path))]
    assert not [f for f in files if f.startswith("s-1__t-1__")], "partial dump left on disk"
    assert [f for f in files if f.startswith("FAILED__")], "loss must leave a tombstone"
    tomb = [p for p in _jsons(str(tmp_path)) if os.path.basename(p).startswith("FAILED__")][0]
    assert "write_error" in json.load(open(tomb, encoding="utf-8"))
