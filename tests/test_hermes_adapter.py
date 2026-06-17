"""End-to-end: drive the Hermes adapter with a fake ctx, simulate a turn that
fails a tool 3x, and assert a real dump artifact lands on disk. Doubles as the
demo / sample-dump generator.
"""
import json
import os
import tempfile

import _bootstrap  # noqa: F401

from macs.dump.adapters.hermes import register
from macs.dump.model import REQUIRED_KEYS


class FakeCtx:
    """Mimics the Hermes plugin ctx: register_hook + config + logger."""
    def __init__(self, config):
        self.config = config
        self.logger = None
        self.hooks = {}

    def register_hook(self, event, cb):
        self.hooks.setdefault(event, []).append(cb)

    def emit(self, event, **payload):
        for cb in self.hooks.get(event, []):
            cb(**payload)


def _run_failing_turn(tmpdir):
    ctx = FakeCtx({"dir": tmpdir, "triggers": [{"predicate": "tool_repeat_fail", "threshold": 3}]})
    register(ctx)
    sid, tid = "sess-abc", "turn-7"

    ctx.emit("on_session_start", session_id=sid, model="claude-opus",
             system_prompt="You are Hermes.", source="telegram",
             telemetry_schema_version="hermes.observer.v1")
    ctx.emit("pre_api_request", session_id=sid, turn_id=tid, api_request_id="api-1",
             model="claude-opus", provider="anthropic", system_prompt="You are Hermes.",
             request=[{"role": "user", "content": "fetch the report"}], approx_input_tokens=120,
             started_at=1000.0)
    for i in range(3):
        ctx.emit("pre_tool_call", session_id=sid, turn_id=tid,
                 tool_call_id=f"t{i}", tool_name="web.fetch", args={"url": "https://x"})
        ctx.emit("post_tool_call", session_id=sid, turn_id=tid,
                 tool_call_id=f"t{i}", tool_name="web.fetch", status="error",
                 duration_ms=15, error_type="Timeout", error_message="upstream timeout")
    return ctx, sid, tid


def test_failing_turn_writes_dump():
    with tempfile.TemporaryDirectory() as tmp:
        _run_failing_turn(tmp)
        files = []
        for root, _dirs, names in os.walk(tmp):
            files += [os.path.join(root, n) for n in names if n.endswith(".json")]
        assert files, "expected a dump file to be written"
        dump = json.load(open(files[0], encoding="utf-8"))
        for k in REQUIRED_KEYS:
            assert k in dump, f"missing {k}"
        assert dump["trigger"]["predicate"] == "tool_repeat_fail"
        assert dump["correlation"]["session_id"] == "sess-abc"
        assert len(dump["tool_calls"]) == 3
        assert all(tc["status"] == "error" for tc in dump["tool_calls"])
        # index.jsonl written too
        idx = [os.path.join(r, n) for r, _d, ns in os.walk(tmp) for n in ns if n == "index.jsonl"]
        assert idx, "expected index.jsonl"


def test_clean_turn_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp})
        register(ctx)
        sid, tid = "s", "t"
        ctx.emit("on_session_start", session_id=sid, model="m")
        ctx.emit("pre_api_request", session_id=sid, turn_id=tid, api_request_id="a", request=[])
        ctx.emit("post_api_request", session_id=sid, turn_id=tid, api_request_id="a",
                 finish_reason="stop", api_duration=0.8, usage={"input": 1, "output": 1})
        files = [n for _r, _d, ns in os.walk(tmp) for n in ns if n.endswith(".json")]
        assert files == [], "clean turn must not produce a dump"


def test_adapter_is_fail_open_on_bad_payload():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp})
        register(ctx)
        # missing keys / weird types must not raise out of the hook
        ctx.emit("post_tool_call")  # no kwargs at all
        ctx.emit("api_request_error", status_code=None, retry_count="x")


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_module(dict(globals())))
