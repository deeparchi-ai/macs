# MACS — Multi-Agent Coordination System

> **MACS is the Agent OS.** It provides the six subsystems every multi-agent
> deployment needs — resource scheduling, access control, audit,
> cross-validation, batch processing, and storage — plus a kernel that
> enforces their decisions.

MACS is modelled on [IBM z/OS](https://www.ibm.com/docs/en/zos). z/OS proved
that a well-designed OS can host hundreds of concurrent programs, enforce
security boundaries, audit every decision, and schedule resources by business
importance — all in one address space. MACS applies the same architecture to
agent systems.

## Architecture

```
Agent (sg-architect, do-developer...)
        │
        ▼
┌───────────────────────────────┐
│  MAEA Middleware (≈ CICS)     │
│  Routing · Session · Lifecycle│
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│  MACS Agent OS (≈ z/OS)       │
│                               │
│  ┌─────────┐ ┌─────────┐     │
│  │ §2 WLM  │ │ §3 Sec  │ ... │
│  │ Resource│ │ Access │     │
│  │ Scheduler│ │Control │     │
│  └─────────┘ └─────────┘     │
│                               │
│  Kernel: Arbiter · Brake · Audit │
└───────────────────────────────┘
```

## Subsystems

| Subsystem | What it does | IBM lineage | Status |
|-----------|-------------|:-----------:|:------:|
| **§2 WLM** | Goal-oriented resource scheduling (CPU + Token) | IBM WLM | ✅ CPU · 🚧 Token |
| **§3 Security** | Access control + behavioral trust + hard constraints | RACF | ✅ |
| **§4 Audit** | Immutable trace chain + decision receipts | SMF | ✅ |
| **§5 XVal** | Dual-model cross-validation for subjective agents | *(Agent-native)* | 📋 |
| **§6 JES** | Batch job scheduling + priority queues | JES2 | 📋 |
| **§7 DFSMS** | Knowledge lifecycle + memory compression | DFSMS | 📋 |
| **§8 VTAM** | Protocol admission + multi-transport | VTAM | 📋 |

Five IBM transplants. One Agent-native (XVal — COBOL compiles; agent outputs
don't).

## Specification

The canonical specification lives in the MAEA Framework repository:

→ **[MACS Governance Specification](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)** (v2.0)

The spec is the single source of truth. This repository holds reference
implementations of the subsystems.

## Subsystem Repos

| Subsystem | Implementation |
|-----------|---------------|
| §2 WLM | [deeparchi-ai/wlm](https://github.com/deeparchi-ai/wlm) — Go, cgroup v2 + PSI, 7 unit tests |
| §4 Audit | [a2a-go PR #365](https://github.com/a2aproject/a2a-go/pull/365) — `a2aext/trace`, 10 unit tests |
| §6 JES | [macs/integrations/jes-gate](integrations/jes-gate/) — WLM-aware cron admission control |

## v0 Artifact: Decision-Chain DUMP (now §4 Audit)

> CICS DUMP/SLIP, for agents.

The first MACS implementation was a recoverability tool: observer hooks that
capture a per-turn ring buffer and, on trigger (tool failure, API error,
latency over budget), freeze the entire decision chain into a self-contained
`macs.dump.v0` artifact. This is now part of the **Audit subsystem (§4)**.

```
macs/dump/
  model.py       # macs.dump.v0 artifact builder + schema constants
  schema.json    # JSON Schema (the interop contract)
  triggers.py    # SLIP-style predicate engine
  collector.py   # per-turn ring buffer → assemble dump on trigger
  sinks.py       # file/jsonl (all writes fail-open)
  adapters/
    hermes.py    # NousResearch/hermes-agent observer hooks → core
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

## Related

- [MAEA Framework](https://github.com/deeparchi-ai/MAEA-Framework) — architecture + specs
- [WLM](https://github.com/deeparchi-ai/wlm) — resource scheduler
- [a2a-go](https://github.com/a2aproject/a2a-go) — A2A protocol Go SDK (+ trace)

---

> *DeepArchi Team · 2026-07-03 · MIT License*
