# MACS Reference Architecture (spec pointer)

Full narrative: *MACS — 企业级多 Agent 架构该长什么样* (DeepArchi · 邝谧).
This file scopes what the reference implementation covers.

## Premise

Managing agents as microservices breaks on four walls (non-determinism,
untrusted executors, contagious failure, black-box decisions). The fix is not a
bigger cluster — it's a governance layer that ports mainframe execution-model
principles onto distributed infrastructure, plus agent-native protocols (A2A).
MACS is an **overlay**, not a platform.

## Six dimensions (eval framework + build targets)

| # | Dimension | Mainframe origin | Ecosystem gap | Impl status |
|---|-----------|------------------|---------------|-------------|
| 1 | Security model | RACF dataset/field-level | tool/param-level only | planned |
| 2 | Scheduling | WLM goal-driven SLA, CICS Dispatcher queues | FIFO / static priority | partial (wlm v0.3.0) |
| 3 | State | CICS Syncpoint, CICSPlex cross-region, DB2 Data Sharing | linear checkpoint / time-travel, no causal-DAG rollback | planned |
| 4 | Audit & governance | SMF | trace-level only | partial (dump+jES+audit-go) |
| 5 | Observability | SMF/RMF zero-config full capture | sampling traces | partial (via dump) |
| 6 | **Recoverability** | **DUMP + SLIP conditional capture** | **absent industry-wide** | **v0 — this repo** |

## v0 scope: Decision-Chain Dump

- **Trigger engine** (`triggers.py`) = SLIP traps: `tool_error`, `tool_repeat_fail`,
  `api_error`, `latency`, `finish_anomaly`, `approval_denied`; extensible
  (`semantic_validation_fail` reserved). Escalation Turn DUMP → Session DUMP
  (Session-level aggregation reserved for v0.x).
- **Artifact** (`macs.dump.v0`, `schema.json`) = Transaction-DUMP analog:
  correlation IDs, Working Storage (system prompt + input), full LLM response,
  tool-call sequence, subagent tree, Task-Control-Block (timings/resources/retries),
  env.
- **Collector** = bounded + TTL'd per-turn ring buffer; evicted on session end.
- **Adapter** = runtime → core event normalization. Hermes first.
- **Invariant**: fail-open everywhere — MACS must never break the host agent.

## Non-goals (red lines)

- Not a new runtime/platform; no cluster to operate.
- Does not capture raw internal objects/memory — it captures the **sanitized
  telemetry view** the runtime already emits (an archival, compliance-friendly
  property, not a limitation to hide).
- Upstream plugin stays self-contained / zero-dependency for mergeability.

## Companion repos

| Repo | Role | MACS dimension | Status |
|------|------|:---:|:---:|
| [deeparchi-ai/wlm](https://github.com/deeparchi-ai/wlm) | Goal-driven scheduling, cgroup v2+PSI, Token budget | §2 Scheduling | v0.3.0, 34 tests |
| [deeparchi-ai/mcp-audit-go](https://github.com/deeparchi-ai/mcp-audit-go) | MCP SEP #3004 audit record — canonical form + hash chain | §4 Audit | 10 tests, cross-lang KAT match |
| [deeparchi-ai/trace-bridge-go](https://github.com/deeparchi-ai/trace-bridge-go) | A2A↔MCP trace context bridge | §4 Audit | 19 tests |
| `macs/integrations/jes-gate/` | WLM-aware cron admission control (Hermes plugin) | §2 Scheduling | In-tree |
| [trace-bridge spec](trace-bridge/spec.md) | Cross-protocol trace propagation v0.1 | §4 Audit | 429 lines, 4 conformance vectors |
