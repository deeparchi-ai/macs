# MACS — Multi-Agent Computing System

A thin **semantic-governance overlay** for existing multi-agent runtimes — **not a
new platform**. MACS does not reinvent middleware (Kafka, Postgres, OpenTelemetry,
durable-execution engines stay underneath); it adds the governance *semantics*
those layers lack, drawn from sixty years of mainframe execution-model design
(CICS, WLM, RACF, SMF/RMF, DUMP/SLIP, Parallel Sysplex).

The reference architecture has six dimensions: **security, scheduling, state,
audit, observability, recoverability**. This repository is the reference
implementation. See [`SPEC.md`](SPEC.md).

## v0: the Decision-Chain Dump (recoverability)

> CICS DUMP/SLIP, for agents.

Observer hooks are an always-on telemetry stream (like SMF/RMF "on by default").
MACS-DUMP keeps a bounded, per-turn ring buffer and — the instant a **SLIP-style
trigger** fires (tool fails N times, API error, latency over budget, abnormal
finish reason, approval denied) — freezes the **entire decision chain** into a
self-contained `macs.dump.v0` artifact: system prompt, full input messages, the
complete LLM response, the tool-call sequence, the subagent tree, timings and
resource/cost state. Logs tell you *what happened*; a dump preserves *what the
world looked like at the instant it happened*.

The dump format (`macs/dump/schema.json`) is the ownable interoperability
contract — runtime-agnostic, so dumps are comparable across frameworks. A
runtime *adapter* maps that runtime's events into the core; **Hermes is adapter #1**.

```
macs/dump/
  model.py       # macs.dump.v0 artifact builder + schema constants
  schema.json    # JSON Schema (the interop contract)
  triggers.py    # SLIP-style predicate engine
  collector.py   # per-turn ring buffer -> assemble dump on trigger
  sinks.py       # file/jsonl (OTel later); all writes fail-open
  adapters/
    base.py      # record -> evaluate -> assemble -> write
    hermes.py    # NousResearch/hermes-agent observer hooks -> core
integrations/hermes-plugin/   # the droppable Hermes plugin (thin shell)
examples/sample_dump.json     # a real artifact from a 3x-tool-timeout turn
```

## Try it

```bash
python tests/test_triggers.py
python tests/test_collector.py
python tests/test_hermes_adapter.py   # end-to-end: fake ctx -> dump on disk
# or, if pytest is installed:  pytest -q
```

## Use with Hermes

`integrations/hermes-plugin/` is a **self-contained, stdlib-only** plugin (no
`pip install`, no dependency on this package) — it's both the dogfood artifact and
the upstream PR artifact:

```bash
cp -r integrations/hermes-plugin  <hermes>/plugins/observability/macs_dump
hermes plugins enable observability/macs_dump
# dumps land in ~/.hermes/macs-dump/<date>/  (+ index.jsonl)
```

It subscribes **read-only** to observer hooks, never touches middleware — **zero
core changes, fail-open** — and was verified against the installed Hermes
**v0.16.0** (registers into the real `PluginManager`, fires through the real
`invoke_hook`). The canonical multi-runtime core lives in `macs/dump/` and shares
the `macs.dump.v0` schema with the vendored plugin.

Upstreaming notes, PR body and the #6741 comment draft:
[`integrations/hermes-plugin/UPSTREAM.md`](integrations/hermes-plugin/UPSTREAM.md).
Relates to Hermes #6741 (structured tracing) and #6642 (unified telemetry).

## Status & ownership

v0, reference implementation. © 2026 DeepArchi (Kuang Mi). MIT.
Home: the **DeepArchi** GitHub org (`DeepArchi/macs`).
