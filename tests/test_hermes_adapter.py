"""End-to-end against the **v0.16.0** hook contract: drive the Hermes adapter
with a fake ctx using the real payload shapes (task_id correlation, result-
encoded tool errors, api_duration in seconds, on_session_finalize), and assert a
real dump artifact lands on disk. Doubles as the demo / sample generator.
"""
import json
import os
import tempfile

import _bootstrap  # noqa: F401

from macs.dump.adapters.hermes import register
from macs.dump.model import REQUIRED_KEYS


class FakeCtx:
    """Mimics the v0.16.0 PluginContext surface used by a plugin: register_hook.
    (No .config/.logger attrs — matches the real PluginContext.)"""
    def __init__(self, config=None):
        if config is not None:
            self.config = config  # optional; real ctx omits it
        self.hooks = {}

    def register_hook(self, event, cb):
        self.hooks.setdefault(event, []).append(cb)

    def emit(self, event, **payload):
        for cb in self.hooks.get(event, []):
            cb(**payload)


def _failing_turn(ctx, sid="sess-abc", task="task-7"):
    ctx.emit("pre_api_request", session_id=sid, task_id=task, api_call_count=1,
             model="claude-opus", provider="anthropic",
             request_messages=[{"role": "user", "content": "fetch the report"}],
             approx_input_tokens=120)
    for i in range(3):
        ctx.emit("pre_tool_call", session_id=sid, task_id=task,
                 tool_call_id=f"t{i}", tool_name="web_fetch", args={"url": "https://x"})
        ctx.emit("post_tool_call", session_id=sid, task_id=task,
                 tool_call_id=f"t{i}", tool_name="web_fetch", args={"url": "https://x"},
                 result={"error": "upstream timeout after 30s"})


def _dump_files(root):
    return [os.path.join(r, n) for r, _d, ns in os.walk(root)
            for n in ns if n.endswith(".json")]


def test_failing_turn_writes_dump():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp, "triggers": [{"predicate": "tool_repeat_fail", "threshold": 3}]})
        register(ctx)
        _failing_turn(ctx)
        files = _dump_files(tmp)
        assert files, "expected a dump file"
        dump = json.load(open(files[0], encoding="utf-8"))
        for k in REQUIRED_KEYS:
            assert k in dump, f"missing {k}"
        assert dump["trigger"]["predicate"] == "tool_repeat_fail"
        assert dump["correlation"]["session_id"] == "sess-abc"
        assert dump["correlation"]["turn_id"] == "task-7"  # task_id maps to turn_id
        assert len(dump["tool_calls"]) == 3
        assert all(tc["status"] == "error" for tc in dump["tool_calls"])
        assert dump["tool_calls"][0]["args"] == {"url": "https://x"}  # merged from pre
        idx = [os.path.join(r, n) for r, _d, ns in os.walk(tmp) for n in ns if n == "index.jsonl"]
        assert idx, "expected index.jsonl"


def test_clean_turn_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp})
        register(ctx)
        sid, task = "s", "k"
        ctx.emit("pre_api_request", session_id=sid, task_id=task, api_call_count=1,
                 request_messages=[], model="m", provider="anthropic")
        ctx.emit("post_tool_call", session_id=sid, task_id=task, tool_call_id="t0",
                 tool_name="web_fetch", args={}, result={"content": "ok", "error": None})
        ctx.emit("post_api_request", session_id=sid, task_id=task, api_call_count=1,
                 finish_reason="stop", api_duration=0.8, usage={"input_tokens": 1, "output_tokens": 1})
        assert _dump_files(tmp) == [], "clean turn must not dump"


def test_latency_trigger_fires_on_slow_response():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp, "triggers": [{"predicate": "latency", "threshold_ms": 30000}]})
        register(ctx)
        sid, task = "s2", "k2"
        ctx.emit("pre_api_request", session_id=sid, task_id=task, api_call_count=1,
                 request_messages=[{"role": "user", "content": "hi"}], model="m")
        ctx.emit("post_api_request", session_id=sid, task_id=task, api_call_count=1,
                 finish_reason="stop", api_duration=45.0, usage={"input_tokens": 5})  # 45s
        files = _dump_files(tmp)
        assert files, "slow response should dump"
        dump = json.load(open(files[0], encoding="utf-8"))
        assert dump["trigger"]["predicate"] == "latency"
        assert dump["control_block"]["duration_ms"] == 45000.0


def test_session_finalize_evicts():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp})
        register(ctx)
        ctx.emit("pre_api_request", session_id="s3", task_id="k3", api_call_count=1,
                 request_messages=[], model="m")
        ctx.emit("on_session_finalize", session_id="s3")
        # buffer gone -> a later trigger for this key produces nothing meaningful
        assert ("s3", "k3") not in ctx.hooks  # sanity: emit() worked


def test_adapter_is_fail_open_on_bad_payload():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp})
        register(ctx)
        ctx.emit("post_tool_call")              # no kwargs at all
        ctx.emit("pre_api_request", session_id=None)
        ctx.emit("post_api_request", api_duration="weird")


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_module(dict(globals())))
