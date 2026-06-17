import _bootstrap  # noqa: F401  (sys.path)

from macs.dump.triggers import DEFAULT_TRIGGERS, evaluate


def test_tool_repeat_fail_fires_on_third():
    events = [
        ("tool_post", {"tool_name": "web.fetch", "status": "error"}),
        ("tool_post", {"tool_name": "web.fetch", "status": "error"}),
    ]
    latest = ("tool_post", {"tool_name": "web.fetch", "status": "error"})
    events.append(latest)
    hit = evaluate(DEFAULT_TRIGGERS, events, latest)
    assert hit is not None and hit.predicate == "tool_repeat_fail"
    assert hit.matched_value == 3 and hit.threshold == 3


def test_tool_repeat_fail_silent_below_threshold():
    events = [("tool_post", {"tool_name": "web.fetch", "status": "error"})]
    latest = events[-1]
    # only api_error/latency etc not present; single failure must not trip repeat
    triggers = [{"predicate": "tool_repeat_fail", "threshold": 3}]
    assert evaluate(triggers, events, latest) is None


def test_different_tools_do_not_accumulate():
    events = [
        ("tool_post", {"tool_name": "a", "status": "error"}),
        ("tool_post", {"tool_name": "b", "status": "error"}),
        ("tool_post", {"tool_name": "a", "status": "error"}),
    ]
    latest = events[-1]
    triggers = [{"predicate": "tool_repeat_fail", "threshold": 3}]
    assert evaluate(triggers, events, latest) is None  # only 2 of "a"


def test_api_error_fires():
    latest = ("api_error", {"status_code": 529, "reason": "overloaded", "retryable": False})
    hit = evaluate(DEFAULT_TRIGGERS, [latest], latest)
    assert hit is not None and hit.predicate == "api_error"
    assert hit.matched_value == 529


def test_latency_fires_over_threshold():
    latest = ("response", {"duration_ms": 45000})
    hit = evaluate([{"predicate": "latency", "threshold_ms": 30000}], [latest], latest)
    assert hit is not None and hit.predicate == "latency" and hit.matched_value == 45000


def test_latency_silent_under_threshold():
    latest = ("response", {"duration_ms": 1200})
    assert evaluate([{"predicate": "latency", "threshold_ms": 30000}], [latest], latest) is None


def test_finish_anomaly_fires():
    latest = ("response", {"finish_reason": "length"})
    hit = evaluate(DEFAULT_TRIGGERS, [latest], latest)
    assert hit is not None and hit.predicate == "finish_anomaly"


def test_clean_response_no_trigger():
    latest = ("response", {"finish_reason": "stop", "duration_ms": 800})
    assert evaluate(DEFAULT_TRIGGERS, [latest], latest) is None


def test_first_matching_trigger_wins_order():
    # api_error listed before latency in DEFAULT_TRIGGERS
    latest = ("api_error", {"status_code": 500})
    hit = evaluate(DEFAULT_TRIGGERS, [latest], latest)
    assert hit.predicate == "api_error"


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_module(dict(globals())))
