# MACS Reference Architecture — Quick Reference

Full specification: [MACS Governance Specification v2.1](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)
(MAEA Framework). This file provides an implementation-status summary for the
eight MACS subsystems.

## Premise

Managing agents as microservices breaks on four walls (non-determinism,
untrusted executors, contagious failure, black-box decisions). The fix is not a
bigger cluster — it's a governance layer that ports mainframe execution-model
principles onto distributed infrastructure, plus agent-native protocols (A2A).
MACS is an **overlay**, not a platform.

## Eight Subsystems

MACS decomposes into eight subsystems mapped to IBM z/OS lineage:

```
                         ┌─────────────────┐
                         │   §8 VTAM       │
                         │ Protocol        │
                         │ Admission       │
                         └────────┬────────┘
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   §2 WLM        │    │   §3 Security    │    │   §6 JES        │
│ Resource        │    │ Access Control   │    │ Batch           │
│ Scheduling      │    │ + Trust Scoring  │    │ Scheduling      │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────┐
│                    MACS Kernel                           │
└────────────┬────────────────────────────────────┬───────┘
             ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│   §5 XVal           │              │   §4 Audit (SMF)    │
│ Cross-Validation    │              │ Immutable Trail     │
└─────────────────────┘              └─────────────────────┘
                                                │
                                                ▼
                                    ┌─────────────────────┐
                                    │   §7 DFSMS          │
                                    │ Knowledge Lifecycle │
                                    └─────────────────────┘
```

## Implementation Status

| # | Subsystem | IBM lineage | Status | Artifacts |
|:--:|-----------|:----------:|:------:|-----------|
| §2 | **WLM** | IBM WLM | partial | [wlm](https://github.com/deeparchi-ai/wlm) v0.3.0 (34 tests), jes-gate |
| §3 | **Security** | RACF | spec + v0.1 | [spec](specs/security-model.md), [macs-security-go](https://github.com/deeparchi-ai/macs-security-go) (13 tests) |
| §3 | **State** | CICS Syncpoint | v0.1 | [macs-state-go](https://github.com/deeparchi-ai/macs-state-go) (12 tests) |
| §4 | **Audit** | SMF | partial | [trace PR #377](https://github.com/a2aproject/a2a-go/pull/377) (20 tests), [mcp-audit-go](https://github.com/deeparchi-ai/mcp-audit-go) (10 tests), [trace-bridge-go](https://github.com/deeparchi-ai/trace-bridge-go) (19 tests), [bridge spec](trace-bridge/spec.md) |
| §5 | **XVal** | *(agent-native)* | v0.1 | [spec](specs/xval-dfsms-vtam.md), [macs-xval-go](https://github.com/deeparchi-ai/macs-xval-go) (11 tests) |
| §6 | **JES** | JES2 | POC | jes-gate (4 scenarios) |
| §7 | **DFSMS** | DFSMS | spec | [spec](specs/xval-dfsms-vtam.md) |
| §8 | **VTAM** | VTAM | spec | [spec](specs/xval-dfsms-vtam.md) |

## §3 State & Rollback (Cross-Cutting)

State management (CICS Syncpoint, causal-DAG rollback) is a cross-cutting
concern spanning Security (§3) and Audit (§4). Design spec:
[state-rollback.md](specs/state-rollback.md).

## v0 Artifact: Decision-Chain DUMP

- **Trigger engine** (`triggers.py`) = SLIP traps: `tool_error`, `tool_repeat_fail`,
  `api_error`, `latency`, `finish_anomaly`, `approval_denied`; extensible.
- **Artifact** (`macs.dump.v0`, `schema.json`) = Transaction-DUMP analog:
  correlation IDs, Working Storage, full LLM response, tool-call sequence,
  subagent tree, Task-Control-Block.
- **Collector** = bounded + TTL'd per-turn ring buffer; evicted on session end.
- **Adapter** = runtime → core event normalization. Hermes first.
- **Invariant**: fail-open everywhere — MACS must never break the host agent.

## Non-Goals (Red Lines)

- Not a new runtime/platform; no cluster to operate.
- Does not capture raw internal objects — captures the sanitized telemetry view.
- Upstream plugin stays self-contained / zero-dependency for mergeability.

---

*DeepArchi · 深度架构 · 2026-07-18*
