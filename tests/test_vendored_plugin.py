"""Validate the self-contained vendored Hermes plugin
(integrations/hermes-plugin/__init__.py) — loaded by file path, so this proves
it has zero dependency on the macs package (stdlib only)."""
import importlib.util
import json
import os
import tempfile

import _bootstrap  # noqa: F401

_PLUGIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "integrations", "hermes-plugin", "__init__.py",
)


def _load():
    spec = importlib.util.spec_from_file_location("macs_dump_vendored", _PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # must not raise -> self-contained
    return mod


class FakeCtx:
    def __init__(self, config=None):
        if config is not None:
            self.config = config
        self.hooks = {}

    def register_hook(self, event, cb):
        self.hooks.setdefault(event, []).append(cb)

    def emit(self, event, **payload):
        for cb in self.hooks.get(event, []):
            cb(**payload)


def _dumps(root):
    return [os.path.join(r, n) for r, _d, ns in os.walk(root) for n in ns if n.endswith(".json")]


def test_vendored_loads_without_macs_package():
    mod = _load()
    assert hasattr(mod, "register")


def test_vendored_failing_turn_dumps():
    mod = _load()
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp, "triggers": [{"predicate": "tool_repeat_fail", "threshold": 3}]})
        mod.register(ctx)
        ctx.emit("pre_api_request", session_id="s", task_id="k", api_call_count=1,
                 request_messages=[{"role": "user", "content": "fetch"}], model="m", provider="anthropic")
        for i in range(3):
            ctx.emit("pre_tool_call", session_id="s", task_id="k", tool_call_id=f"t{i}",
                     tool_name="web_fetch", args={"url": "x"})
            ctx.emit("post_tool_call", session_id="s", task_id="k", tool_call_id=f"t{i}",
                     tool_name="web_fetch", args={"url": "x"}, result={"error": "timeout"})
        files = _dumps(tmp)
        assert files, "vendored plugin produced no dump"
        d = json.load(open(files[0], encoding="utf-8"))
        assert d["schema"] == "macs.dump.v0"
        assert d["trigger"]["predicate"] == "tool_repeat_fail"
        assert len(d["tool_calls"]) == 3 and all(t["status"] == "error" for t in d["tool_calls"])


def test_vendored_clean_turn_no_dump():
    mod = _load()
    with tempfile.TemporaryDirectory() as tmp:
        ctx = FakeCtx({"dir": tmp})
        mod.register(ctx)
        ctx.emit("pre_api_request", session_id="s", task_id="k", api_call_count=1,
                 request_messages=[], model="m")
        ctx.emit("post_api_request", session_id="s", task_id="k", api_call_count=1,
                 finish_reason="stop", api_duration=0.5, usage={"input_tokens": 1})
        assert _dumps(tmp) == []


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_module(dict(globals())))
