import _bootstrap  # noqa: F401

from macs.dump.collector import TurnCollector
from macs.dump.model import REQUIRED_KEYS


def _seed_turn(c, key):
    c.record(key, "request", {
        "api_request_id": "api-1", "model": "claude", "provider": "anthropic",
        "system_prompt": "You are Hermes.", "input_messages": [{"role": "user", "content": "hi"}],
        "approx_input_tokens": 42, "started_at": 1000.0,
    })
    c.record(key, "tool_pre", {"tool_call_id": "t1", "tool_name": "web.fetch", "args": {"url": "x"}})
    c.record(key, "tool_post", {"tool_call_id": "t1", "tool_name": "web.fetch",
                                 "status": "error", "duration_ms": 12, "error_type": "Timeout",
                                 "error_message": "boom"})
    c.record(key, "response", {"api_request_id": "api-1", "assistant_message": {"role": "assistant", "content": "..."},
                                "finish_reason": "stop", "usage": {"input": 42, "output": 10},
                                "duration_ms": 900})


def test_assemble_has_all_required_keys():
    c = TurnCollector()
    key = ("s1", "turn-1")
    c.open("s1", {"hermes_version": "9.9", "platform": "cli"})
    _seed_turn(c, key)
    dump = c.assemble(key, trigger={"predicate": "tool_error"},
                      now_iso="2026-06-16T00:00:00+00:00", dump_id="fixed")
    for k in REQUIRED_KEYS:
        assert k in dump, f"missing {k}"
    assert dump["dump_id"] == "fixed"
    assert dump["schema"] == "macs.dump.v0"


def test_assemble_reconstructs_chain():
    c = TurnCollector()
    key = ("s1", "turn-1")
    c.open("s1", {"hermes_version": "9.9", "platform": "telegram"})
    _seed_turn(c, key)
    dump = c.assemble(key, trigger={"predicate": "tool_error"})
    assert dump["correlation"]["session_id"] == "s1"
    assert dump["correlation"]["turn_id"] == "turn-1"
    assert dump["correlation"]["api_request_id"] == "api-1"
    assert dump["context"]["system_prompt"] == "You are Hermes."
    assert dump["context"]["model"] == "claude"
    assert dump["llm_response"]["finish_reason"] == "stop"
    assert len(dump["tool_calls"]) == 1
    tc = dump["tool_calls"][0]
    assert tc["tool_name"] == "web.fetch" and tc["status"] == "error"
    assert tc["args"] == {"url": "x"}  # merged from tool_pre
    assert dump["control_block"]["api_call_count"] == 1
    assert dump["control_block"]["tool_call_count"] == 1
    assert dump["env"]["platform"] == "telegram"


def test_ttl_eviction_drops_stale_turns():
    c = TurnCollector(ttl_s=10)
    key = ("s1", "old")
    c.record(key, "request", {"model": "m"}, now=0.0)
    # a later event triggers GC; stale buffer (created at 0) should be dropped at now>10
    c.record(("s1", "new"), "request", {"model": "m"}, now=100.0)
    assert c.view(("s1", "old")) == []
    assert c.view(("s1", "new")) != []


def test_evict_session_clears_buffers():
    c = TurnCollector()
    c.open("s1", {})
    c.record(("s1", "t1"), "request", {"model": "m"})
    c.record(("s1", "t2"), "request", {"model": "m"})
    c.evict("s1")
    assert c.view(("s1", "t1")) == [] and c.view(("s1", "t2")) == []


def test_maxlen_is_bounded():
    c = TurnCollector(maxlen=5)
    key = ("s1", "t1")
    for i in range(20):
        c.record(key, "tool_post", {"tool_call_id": str(i), "tool_name": "x", "status": "ok"})
    assert len(c.view(key)) == 5  # ring buffer cap


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_module(dict(globals())))
