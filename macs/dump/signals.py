"""Aggregate macs.dump.v0 artifacts into daily governance signals.

The dump sink answers "what did this one turn look like"; this module answers
"what does a day look like" — the aggregation that Gauge (§9, RMF/NetView) is
supposed to produce and that a sessions table cannot: tool failure bursts,
latency overruns, and context bloat.

Design notes
------------
* **Degraded files are counted, not dropped.** A dump that fails strict JSON
  parsing is still scanned with a tolerant prefix reader, and its count feeds
  ``parse_rate`` — a sink that silently produces 100% unreadable artifacts
  (observed once: 556/556 files truncated mid-write) must be visible in the
  daily report, never silent.
* **Fail-open, no dependencies.** Stdlib only; never raises out of ``scan``.
* Aggregation only — no interpretation, no thresholds, no verdicts.

CLI
---
    python -m macs.dump.signals --dir ~/.hermes/macs-dump
    python -m macs.dump.signals --dir /path/quarantine --day 2026-10-16
    python -m macs.dump.signals --dir /path/quarantine --json
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence

__all__ = ["scan", "render"]

_PRED = re.compile(r'"predicate":\s*"([A-Za-z_]+)"')
_DETAIL = re.compile(r'"detail":\s*"([^"]*)"')
_VAL = re.compile(r'"matched_value":\s*([0-9.]+)')
_THR = re.compile(r'"threshold":\s*([0-9.]+)')
_SESS = re.compile(r'"session_id":\s*"([^"]*)"')
_TOK = re.compile(r'"approx_input_tokens":\s*([0-9]+)')
_TS = re.compile(r'"captured_at":\s*"([^"]*)"')


def _pct(values: "Sequence[float]", q: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[idx]


def _tolerant(text: str) -> Dict[str, Any]:
    """Extract the fields we aggregate from a possibly truncated dump."""
    out: Dict[str, Any] = {}
    if (m := _PRED.search(text)):
        out["predicate"] = m.group(1)
    if (m := _DETAIL.search(text)):
        out["detail"] = m.group(1)
    if (m := _VAL.search(text)):
        try:
            out["matched_value"] = float(m.group(1))
        except ValueError:
            pass
    if (m := _THR.search(text)):
        try:
            out["threshold"] = float(m.group(1))
        except ValueError:
            pass
    if (m := _SESS.search(text)):
        out["session_id"] = m.group(1)
    if (m := _TOK.search(text)):
        try:
            out["approx_input_tokens"] = int(m.group(1))
        except ValueError:
            pass
    if (m := _TS.search(text)):
        out["captured_at"] = m.group(1)
    return out


def _read(path: str):
    """Return (record, valid_json). Never raises."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None, False
    try:
        obj = json.loads(text)
    except Exception:
        rec = _tolerant(text)
        rec["_file"] = path
        return (rec if rec.get("predicate") else None), False
    trig = obj.get("trigger") or {}
    corr = obj.get("correlation") or {}
    ctx = obj.get("context") or {}
    return {
        "predicate": trig.get("predicate"),
        "detail": trig.get("detail"),
        "matched_value": trig.get("matched_value"),
        "threshold": trig.get("threshold"),
        "session_id": corr.get("session_id"),
        "approx_input_tokens": ctx.get("approx_input_tokens"),
        "captured_at": obj.get("captured_at"),
        "_file": path,
    }, True


def _day_dirs(base: str, day: Optional[str]) -> List[str]:
    if day:
        d = os.path.join(os.path.expanduser(base), day)
        return [d] if os.path.isdir(d) else []
    root = os.path.expanduser(base)
    if not os.path.isdir(root):
        return []
    return sorted(os.path.join(root, n) for n in os.listdir(root)
                  if os.path.isdir(os.path.join(root, n)) and n[:2] == "20")


def scan(base_dir: str, day: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate dumps under ``base_dir`` (optionally a single ``day`` = YYYY-MM-DD)."""
    files: List[str] = []
    for d in _day_dirs(base_dir, day):
        for n in sorted(os.listdir(d)):
            if n.endswith(".json"):
                files.append(os.path.join(d, n))

    total = valid = degraded = 0
    predicates: Counter = Counter()
    tools: Counter = Counter()
    by_day: Counter = Counter()
    latency: List[float] = []
    thresholds: Dict[str, float] = defaultdict(float)
    tokens: List[int] = []
    sessions: Counter = Counter()
    cron_sessions: set = set()
    interactive_sessions: set = set()

    for f in files:
        rec, ok = _read(f)
        if rec is None:
            total += 1
            degraded += 1
            continue
        total += 1
        valid += 1 if ok else 0
        degraded += 0 if ok else 1
        p = rec.get("predicate") or "?"
        predicates[p] += 1
        detail = rec.get("detail") or ""
        if p == "tool_repeat_fail" and detail:
            tools[detail.replace("tool=", "")] += 1
        if p == "latency" and isinstance(rec.get("matched_value"), (int, float)):
            latency.append(float(rec["matched_value"]))
        if isinstance(rec.get("threshold"), (int, float)) and rec["threshold"]:
            thresholds[p] = float(rec["threshold"])
        if isinstance(rec.get("approx_input_tokens"), int):
            tokens.append(rec["approx_input_tokens"])
        sid = rec.get("session_id") or "?"
        sessions[sid] += 1
        (cron_sessions if sid.startswith("cron_") else interactive_sessions).add(sid)
        # Group by the sink's folder (= local date); captured_at is UTC and would
        # split a local evening across two report days.
        by_day[os.path.basename(os.path.dirname(f))] += 1
    return {
        "base_dir": os.path.expanduser(base_dir),
        "day": day,
        "files": total,
        "valid_json": valid,
        "degraded": degraded,
        "parse_rate": round(valid / total, 3) if total else None,
        "predicates": dict(predicates.most_common()),
        "tool_failures": dict(tools.most_common(10)),
        "latency_ms": {
            "n": len(latency),
            "threshold": thresholds.get("latency"),
            "p50": _pct(latency, 0.50),
            "p95": _pct(latency, 0.95),
            "max": max(latency) if latency else None,
        },
        "input_tokens": {
            "n": len(tokens),
            "p50": _pct(tokens, 0.50),
            "p90": _pct(tokens, 0.90),
            "max": max(tokens) if tokens else None,
        },
        "sessions": {"distinct": len(sessions), "cron": len(cron_sessions),
                     "interactive": len(interactive_sessions)},
        "by_day": dict(sorted(by_day.items())),
    }


def render(sig: Dict[str, Any]) -> str:
    """One compact block for the daily governance report."""
    if not sig.get("files"):
        return "### 质量维度实测（dump）\n  今日无 dump 触发（沉默即正常，或插件未生效）"
    lines = ["### 质量维度实测（dump 取证层）"]
    pr = sig["parse_rate"]
    flag = "✅" if pr == 1.0 else ("🚨" if pr == 0 else "⚠️")
    lines.append(f"  可解析率 {flag} {pr:.0%}（{sig['valid_json']}/{sig['files']}，降级 {sig['degraded']}）")
    preds = " · ".join(f"{k}={v}" for k, v in sig["predicates"].items())
    lines.append(f"  触发 {sig['files']} 次：{preds}")
    lat = sig["latency_ms"]
    if lat["n"]:
        lines.append(f"  延迟超阈 {lat['n']} 次 · p50={lat['p50']:.0f}ms p95={lat['p95']:.0f}ms "
                     f"max={lat['max']:.0f}ms（阈 {lat['threshold']:.0f}ms）")
    if sig["tool_failures"]:
        top = " · ".join(f"{k}×{v}" for k, v in list(sig["tool_failures"].items())[:5])
        lines.append(f"  工具连败 Top：{top}")
    tk = sig["input_tokens"]
    if tk["n"]:
        lines.append(f"  输入上下文 p50={tk['p50']:,.0f} p90={tk['p90']:,.0f} max={tk['max']:,}")
    ss = sig["sessions"]
    lines.append(f"  会话 {ss['distinct']} 个（交互 {ss['interactive']} / cron {ss['cron']}）")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Aggregate macs.dump artifacts into daily signals")
    ap.add_argument("--dir", default="~/.hermes/macs-dump")
    ap.add_argument("--day", default=None, help="YYYY-MM-DD (omit for all days)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    sig = scan(a.dir, a.day)
    print(json.dumps(sig, ensure_ascii=False, indent=2) if a.json else render(sig))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
