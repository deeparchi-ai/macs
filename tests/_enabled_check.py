"""Verify the *enabled* macs_dump plugin loads via Hermes real discovery and
writes to the production dump dir. Fires a marked synthetic turn, asserts the
artifact, then deletes it. Run with the Hermes venv python."""
import glob
import json
import os
import sys

HERMES = "/home/kuang/.hermes/hermes-agent"
if HERMES not in sys.path:
    sys.path.insert(0, HERMES)

MARK = "macs-selfcheck-DELETEME"
DUMP_DIR = os.path.expanduser("~/.hermes/macs-dump")


def main():
    from hermes_cli.plugins import discover_plugins, invoke_hook, has_hook
    discover_plugins(force=True)
    if not has_hook("post_tool_call"):
        print("FAIL: post_tool_call has no callbacks after discovery")
        return 1

    invoke_hook("pre_api_request", session_id=MARK, task_id="t1", api_call_count=1,
                request_messages=[{"role": "user", "content": "selfcheck"}], model="m", provider="p")
    for i in range(3):
        invoke_hook("post_tool_call", session_id=MARK, task_id="t1", tool_call_id=f"c{i}",
                    tool_name="web_fetch", args={"u": "x"}, result={"error": "selfcheck timeout"})

    hits = glob.glob(os.path.join(DUMP_DIR, "**", f"{MARK}*__*.json"), recursive=True)
    if not hits:
        print("FAIL: enabled plugin produced no dump in", DUMP_DIR)
        return 1
    d = json.load(open(hits[0], encoding="utf-8"))
    ok = (d.get("schema") == "macs.dump.v0"
          and d["trigger"]["predicate"] == "tool_repeat_fail"
          and len(d["tool_calls"]) == 3)
    print("ENABLED-OK" if ok else "ENABLED-PARTIAL",
          "| dumps_written:", len(hits), "| trigger:", d["trigger"]["predicate"],
          "| tools:", len(d["tool_calls"]))
    for f in hits:           # clean up the synthetic selfcheck dumps
        os.remove(f)
    print("cleaned", len(hits), "selfcheck dump(s)")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print("ERROR during enabled-check:", repr(e))
        raise SystemExit(2)
