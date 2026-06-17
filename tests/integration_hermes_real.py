"""REAL integration smoke: register the macs_dump adapter into the *actual*
Hermes PluginManager and fire events through the *actual* ``invoke_hook``
dispatcher (fail-open, injects telemetry_schema_version), asserting a dump
artifact is produced.

Run with the Hermes venv python, e.g.:
    /home/kuang/.hermes/hermes-agent/venv/bin/python tests/integration_hermes_real.py

Skips (exit 0) if the Hermes plugin system isn't importable, so it's portable.
"""
import glob
import json
import os
import shutil
import sys
import tempfile

HERMES = os.environ.get("HERMES_ROOT", "/home/kuang/.hermes/hermes-agent")
MACS = os.environ.get("MACS_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (MACS, HERMES):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main() -> int:
    try:
        from hermes_cli.plugins import get_plugin_manager, invoke_hook, has_hook
    except Exception as e:  # noqa: BLE001
        print("SKIP: Hermes plugin system not importable:", repr(e))
        return 0

    from macs.dump.adapters.hermes import register

    mgr = get_plugin_manager()
    tmp = tempfile.mkdtemp(prefix="macs-real-")

    # Minimal ctx mirroring PluginContext.register_hook (appends to the real
    # manager's hook registry that the real invoke_hook dispatches from).
    class RealCtx:
        def __init__(self, manager, config):
            self._manager = manager
            self.config = config

        def register_hook(self, name, cb):
            self._manager._hooks.setdefault(name, []).append(cb)

    ctx = RealCtx(mgr, {"dir": tmp, "triggers": [{"predicate": "tool_repeat_fail", "threshold": 3}]})
    register(ctx)

    assert has_hook("post_tool_call"), "macs_dump did not register into the real manager"

    sid, task = "real-sess", "real-task"
    invoke_hook("pre_api_request", session_id=sid, task_id=task, api_call_count=1,
                request_messages=[{"role": "user", "content": "fetch the q3 report"}],
                model="claude-opus", provider="anthropic")
    for i in range(3):
        invoke_hook("pre_tool_call", session_id=sid, task_id=task,
                    tool_call_id=f"t{i}", tool_name="web_fetch", args={"url": "https://x"})
        invoke_hook("post_tool_call", session_id=sid, task_id=task,
                    tool_call_id=f"t{i}", tool_name="web_fetch", args={"url": "https://x"},
                    result={"error": "upstream timeout after 30s"})

    files = glob.glob(os.path.join(tmp, "**", "*.json"), recursive=True)
    try:
        assert files, "no dump produced via REAL invoke_hook dispatcher"
        d = json.load(open(files[0], encoding="utf-8"))
        assert d["schema"] == "macs.dump.v0"
        assert d["trigger"]["predicate"] == "tool_repeat_fail"
        assert d["correlation"]["session_id"] == sid
        assert d["correlation"]["turn_id"] == task
        assert len(d["tool_calls"]) == 3 and all(t["status"] == "error" for t in d["tool_calls"])
        assert d["source_telemetry_schema"] == "hermes.observer.v1"
        print("REAL-OK: dump produced via the actual PluginManager.invoke_hook")
        print("  file   :", files[0])
        print("  trigger:", d["trigger"])
        print("  tools  :", len(d["tool_calls"]), "all error =",
              all(t["status"] == "error" for t in d["tool_calls"]))
        print("  context.input_messages present:", bool(d["context"]["input_messages"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        # leave the real manager clean
        for name in list(mgr._hooks):
            mgr._hooks[name] = [cb for cb in mgr._hooks[name]
                                if getattr(cb, "__module__", "") != "macs.dump.adapters.hermes"]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
