"""macs.dump.signals — daily aggregation over dump artifacts."""
import json
import os
import tempfile

import _bootstrap  # noqa: F401

from macs.dump import signals


def _valid_dump(predicate, value=None, threshold=None, session="s1", tokens=1000, detail=None):
    return {
        "dump_id": f"id-{predicate}-{value}",
        "schema": "macs.dump.v0",
        "captured_at": "2026-10-24T02:00:00+00:00",
        "trigger": {"predicate": predicate, "detail": detail,
                    "matched_value": value, "threshold": threshold},
        "correlation": {"session_id": session, "turn_id": "t1"},
        "context": {"approx_input_tokens": tokens},
        "llm_response": {"assistant_message": {"content": "ok"}},
    }


def _write(directory, name, payload):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, name), "w", encoding="utf-8") as f:
        if isinstance(payload, str):
            f.write(payload)
        else:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def test_scan_aggregates_and_flags_degraded_files():
    with tempfile.TemporaryDirectory() as tmp:
        day = os.path.join(tmp, "2026-10-24")
        _write(day, "a.json", _valid_dump("latency", 40000, 30000, "s1", 1000))
        _write(day, "b.json", _valid_dump("latency", 60000, 30000, "s1", 3000))
        _write(day, "c.json", _valid_dump("tool_repeat_fail", 3, 3, "cron_x", 500,
                                          detail="tool=terminal"))
        # a truncated artifact, as produced by the pre-fix writer
        _write(day, "d.json", '{\n  "dump_id": "x",\n  "trigger": {\n    "predicate": "latency",\n'
                              '    "detail": "api_duration",\n    "matched_value": 90000,\n'
                              '    "threshold": 30000\n  },\n  "correlation": {"session_id": "s2"},\n'
                              '  "llm_response": { "assistant_message": ')

        sig = signals.scan(tmp)

        assert sig["files"] == 4
        assert sig["valid_json"] == 3 and sig["degraded"] == 1
        assert sig["parse_rate"] == 0.75
        assert sig["predicates"]["latency"] == 3          # degraded file still counted
        assert sig["predicates"]["tool_repeat_fail"] == 1
        assert sig["tool_failures"] == {"terminal": 1}
        assert sig["latency_ms"]["n"] == 3                # degraded file's value kept
        assert sig["latency_ms"]["max"] == 90000
        assert sig["latency_ms"]["threshold"] == 30000
        assert sig["input_tokens"]["max"] == 3000
        assert sig["sessions"] == {"distinct": 3, "cron": 1, "interactive": 2}
        assert sig["by_day"] == {"2026-10-24": 4}


def test_scan_single_day_and_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        _write(os.path.join(tmp, "2026-10-23"), "a.json", _valid_dump("latency", 31000, 30000))
        _write(os.path.join(tmp, "2026-10-24"), "b.json", _valid_dump("latency", 32000, 30000))
        only = signals.scan(tmp, day="2026-10-24")
        assert only["files"] == 1 and only["by_day"] == {"2026-10-24": 1}

    with tempfile.TemporaryDirectory() as tmp:
        sig = signals.scan(tmp)
        assert sig["files"] == 0 and sig["parse_rate"] is None
        assert "无 dump 触发" in signals.render(sig)


def test_render_reports_parse_rate_and_top_failures():
    with tempfile.TemporaryDirectory() as tmp:
        day = os.path.join(tmp, "2026-10-24")
        _write(day, "a.json", _valid_dump("tool_repeat_fail", 3, 3, detail="tool=terminal"))
        _write(day, "b.json", _valid_dump("tool_repeat_fail", 4, 3, detail="tool=web_search"))
        out = signals.render(signals.scan(tmp))
        assert "可解析率" in out and "100%" in out
        assert "terminal×1" in out and "web_search×1" in out


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_module(dict(globals())))
