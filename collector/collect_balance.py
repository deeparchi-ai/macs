#!/usr/bin/env python3
"""MACS v1 Balance collector for DeepSeek and Kimi/Moonshot."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

DATA_FILE = Path.home() / "projects" / "macs" / "data" / "balance_snapshots.jsonl"
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

PROVIDERS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "url": "https://api.deepseek.com/user/balance",
        "extract": lambda payload: {
            "balance": float(payload["balance_infos"][0]["total_balance"]),
            "currency": payload["balance_infos"][0].get("currency", "CNY"),
        },
    },
    "kimi": {
        "url": "https://api.moonshot.cn/v1/users/me/balance",
        "extract": lambda payload: {
            "balance": float(payload["data"]["cash_balance"]),
            "currency": payload["data"].get("currency", "CNY"),
        },
    },
}


def load_existing_keys(path: Path) -> set[tuple[str, int]]:
    """Return existing (provider, ts) tuples to avoid duplicates."""
    keys: set[tuple[str, int]] = set()
    if not path.exists():
        return keys
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                keys.add((record["provider"], record["ts"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return keys


def fetch_balance(
    provider: str,
    config: dict[str, Any],
    existing_keys: set[tuple[str, int]],
) -> dict[str, Any] | None:
    """Fetch a single provider balance and return a snapshot line, or None if duplicate."""
    api_key = os.environ.get(f"{provider.upper()}_API_KEY")
    if not api_key:
        raise RuntimeError(f"Missing environment variable {provider.upper()}_API_KEY")

    ts = int(time.time())
    key = (provider, ts)
    if key in existing_keys:
        return None

    try:
        resp = requests.get(
            config["url"],
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        snapshot = {"provider": provider, "ts": ts, **config["extract"](payload)}
    except requests.exceptions.Timeout as exc:
        snapshot = {"provider": provider, "ts": ts, "error": f"timeout: {exc}"}
    except requests.exceptions.RequestException as exc:
        snapshot = {"provider": provider, "ts": ts, "error": f"request_error: {exc}"}
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        snapshot = {"provider": provider, "ts": ts, "error": f"parse_error: {exc}"}

    return snapshot


def main() -> None:
    existing_keys = load_existing_keys(DATA_FILE)
    new_lines: list[dict[str, Any]] = []

    for provider, config in PROVIDERS.items():
        snapshot = fetch_balance(provider, config, existing_keys)
        if snapshot is not None:
            new_lines.append(snapshot)
            existing_keys.add((snapshot["provider"], snapshot["ts"]))

    if new_lines:
        with DATA_FILE.open("a", encoding="utf-8") as f:
            for line in new_lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    for line in new_lines:
        print(json.dumps(line, ensure_ascii=False))


if __name__ == "__main__":
    main()
