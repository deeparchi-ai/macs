# MACS — Multi-Agent Coordination System

> **MACS is the Agent OS.** It provides the eight subsystems every multi-agent
> deployment needs — resource scheduling, access control, audit,
> cross-validation, batch processing, knowledge management, and network
> admission — plus a kernel that enforces their decisions.

MACS is modelled on [IBM z/OS](https://www.ibm.com/docs/en/zos). z/OS proved
that a well-designed OS can host hundreds of concurrent programs, enforce
security boundaries, audit every decision, and schedule resources by business
importance — all in one address space. MACS applies the same architecture to
agent systems.

## Architecture

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

## Subsystems

| # | Subsystem | What it does | IBM lineage | Status |
|:--:|-----------|-------------|:----------:|:------:|
| §2 | **WLM** | Goal-oriented resource scheduling (CPU + Token) | IBM WLM | ✅ CPU · 🚧 Token |
| §3 | **Security** | RACF-style access control + behavioral trust scoring | RACF | 📐 spec · ✅ v0.1 Go · 🚧 trust |
| §3 | **State** | CICS Syncpoint — causal-DAG rollback + two-phase commit | CICS Syncpoint | ✅ v0.1 Go |
| §4 | **Audit** | W3C traceparent audit trail + MCP records + cross-protocol bridge | SMF | ✅ trace · ✅ bridge · ✅ mcp-audit |
| §5 | **XVal** | Dual-model cross-validation for subjective agents | *(agent-native)* | 📐 spec · ✅ v0.1 Go |
| §6 | **JES** | Batch job scheduling + priority admission | JES2 | ✅ jes-gate POC |
| §7 | **DFSMS** | Knowledge lifecycle + memory compression | DFSMS | ✅ v0.1 Go |
| §8 | **VTAM** | Protocol admission + multi-transport routing | VTAM | ✅ v0.1 Go |

Five IBM transplants. Three Agent-native additions (XVal — COBOL programs don't hallucinate;
DFSMS knowledge semantics — confidence/superseded_by; VTAM — A2A/MCP/Feishu coexistence).

## Specification

The canonical specification is in the MAEA Framework repository:

→ **[MACS Governance Specification v2.1](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)**

The governance spec includes the subsystem topology, failure model, W3C traceparent
propagation, cross-protocol bridge, implementation status, and 24-term glossary.

## Implementation Repos

| Subsystem | Repository | Tests |
|-----------|-----------|:-----:|
| §2 WLM | [deeparchi-ai/wlm](https://github.com/deeparchi-ai/wlm) — Go, cgroup v2 + PSI | 34 |
| §3 Security | [deeparchi-ai/macs-security-go](https://github.com/deeparchi-ai/macs-security-go) — RACF tool profiles | 13 |
| §3 State | [deeparchi-ai/macs-state-go](https://github.com/deeparchi-ai/macs-state-go) — Causal-DAG rollback | 12 |
| §4 Audit — Trace | [a2a-go PR #377](https://github.com/a2aproject/a2a-go/pull/377) — W3C traceparent | 20 |
| §4 Audit — MCP | [deeparchi-ai/mcp-audit-go](https://github.com/deeparchi-ai/mcp-audit-go) — SEP #3004 | 10 |
| §4 Audit — Bridge | [deeparchi-ai/trace-bridge-go](https://github.com/deeparchi-ai/trace-bridge-go) — A2A↔MCP | 19 |
| §5 XVal | [deeparchi-ai/macs-xval-go](https://github.com/deeparchi-ai/macs-xval-go) — dual-model verification | 11 |
| §6 JES | [macs/integrations/jes-gate](integrations/jes-gate/) — WLM-aware cron admission | — |
| §7 DFSMS | [deeparchi-ai/macs-dfsms-go](https://github.com/deeparchi-ai/macs-dfsms-go) — tiered context lifecycle | 13 |
| §8 VTAM | [deeparchi-ai/macs-vtam-go](https://github.com/deeparchi-ai/macs-vtam-go) — transport routing + admission | 16 |

## Design Specs (pre-implementation)

| Spec | Subsystem | 
|------|:---:|
| [security-model.md](specs/security-model.md) | §3 Tool profiles, param scopes, program pathing |
| [state-rollback.md](specs/state-rollback.md) | §3 Causal-DAG rollback + two-phase commit |
| [xval-dfsms-vtam.md](specs/xval-dfsms-vtam.md) | §5 XVal · §7 DFSMS · §8 VTAM |
| [trace-bridge/spec.md](trace-bridge/spec.md) | §4 A2A↔MCP trace context bridge (429 lines) |

## v0 Artifact: Decision-Chain DUMP

> CICS DUMP/SLIP, for agents.

The first MACS implementation: observer hooks that capture a per-turn ring buffer
and, on trigger (tool failure, API error, latency over budget), freeze the entire
decision chain into a self-contained `macs.dump.v0` artifact.

```
macs/dump/
  model.py       # macs.dump.v0 artifact builder + schema constants
  schema.json    # JSON Schema (the interop contract)
  triggers.py    # SLIP-style predicate engine
  collector.py   # per-turn ring buffer → assemble dump on trigger
  sinks.py       # file/jsonl (all writes fail-open)
  adapters/
    hermes.py    # Hermes agent observer hooks → core
integrations/hermes-plugin/   # drop-in Hermes plugin (stdlib-only)
```

**Quick test:**

```bash
python tests/test_triggers.py
python tests/test_collector.py
python tests/test_hermes_adapter.py
# or: pytest -q
```

**Hermes install:**

```bash
cp -r integrations/hermes-plugin  <hermes>/plugins/observability/macs_dump
hermes plugins enable observability/macs_dump
# dumps land in ~/.hermes/macs-dump/<date>/  (+ index.jsonl)
```

Zero core changes. Fail-open. Read-only observer hooks.

## Non-Goals

- Not a new runtime/platform; no cluster to operate.
- Does not capture raw internal objects — captures the sanitized telemetry view.
- Upstream plugin stays self-contained / zero-dependency for mergeability.

## Related

- [MAEA Framework](https://github.com/deeparchi-ai/MAEA-Framework) — architecture + canonical spec
- [WLM](https://github.com/deeparchi-ai/wlm) — resource scheduler
- [a2a-go](https://github.com/a2aproject/a2a-go) — A2A protocol Go SDK (+ trace)

---

> *DeepArchi Team · 2026-07-18 · MIT License*
