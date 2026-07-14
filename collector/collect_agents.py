#!/usr/bin/env python3
"""MACS v1: Agent session hygiene token collector.

Scans all Hermes agent logs for lines like:
    2026-07-02 07:08:01,466 INFO gateway.run: Session hygiene: 407 messages, ~239,982 tokens (actual) — auto-compressing ...

Appends unique {agent, ts} records to:
    ~/projects/macs/data/agent_tokens.jsonl
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


LOG_GLOB = Path.home() / ".hermes" / "profiles" / "*" / "logs" / "agent.log"
OUTPUT_DIR = Path.home() / "projects" / "macs" / "data"
OUTPUT_FILE = OUTPUT_DIR / "agent_tokens.jsonl"

PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ INFO.*"
    r"Session hygiene: (\d+) messages, ~([\d,]+) tokens \(actual\)"
)


def load_existing_keys(path: Path) -> set[tuple[str, str]]:
    """Read existing JSONL and return set of (agent, ts) already recorded."""
    seen: set[tuple[str, str]] = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                seen.add((record["agent"], record["ts"]))
            except (json.JSONDecodeError, KeyError) as exc:
                print(f"Warning: skipping malformed line {line_no} in {path}: {exc}")
    return seen


def collect() -> list[dict]:
    """Scan agent logs and return list of new records."""
    seen = load_existing_keys(OUTPUT_FILE)
    records: list[dict] = []

    for log_path in sorted(Path.home().glob(".hermes/profiles/*/logs/agent.log")):
        agent = log_path.parent.parent.name
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if "Session hygiene" not in line or "(actual)" not in line:
                    continue
                match = PATTERN.match(line)
                if not match:
                    continue
                ts_raw, messages_raw, tokens_raw = match.groups()
                ts = ts_raw.replace(" ", "T")
                key = (agent, ts)
                if key in seen:
                    continue
                seen.add(key)
                records.append(
                    {
                        "agent": agent,
                        "ts": ts,
                        "messages": int(messages_raw),
                        "tokens": int(tokens_raw.replace(",", "")),
                    }
                )

    return records


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = collect()
    if not records:
        print("No new agent token records found.")
        return

    with OUTPUT_FILE.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Appended {len(records)} new records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
