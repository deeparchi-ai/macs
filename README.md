# MACS — Multi-Agent Coordination System

> **MACS is the Agent OS.** Thirteen subsystems — from resource regulation to
> tri-model cross-validation to crash recovery — modelled on IBM z/OS, built
> for multi-agent networks.

Canonical specification: [MACS Governance Specification v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)

## Subsystems

| § | Name | Role | z/OS | Status |
|:--:|------|------|:---:|:------:|
| §2 | **Regulator** | Goal scheduling + token budget + model failover | WLM | ✅ CPU · 🚧 Token |
| §3 | **Sanctum** | Access control + trust scoring + hard constraints | RACF | ✅ v0.1 Go · 🚧 trust |
| §3b | **Loom** | Causal-DAG rollback + two-phase commit | CICS | ✅ v0.1 Go |
| §4 | **Chronicle** | Audit trail + W3C trace + cross-protocol bridge | SMF | ✅ 4 components |
| §5 | **XVal** | **Tri-model** cross-validation + vendor failover | *(native)* | 🚧 v0.1 → tri-model |
| §6 | **Cadence** | Batch scheduling + job output management | JES2+SDSF | ✅ POC |
| §7 | **Curator** | Knowledge lifecycle + compression + backup | DFSMS+dss | ✅ v0.1 Go |
| §8 | **Nexus** | Protocol admission + multi-transport routing | VTAM | ✅ v0.1 Go |
| §9 | **Gauge** | Performance metrics + cross-vendor health | RMF+NetView | 📋 spec |
| §10 | **Seal** | Identity registry + certificates + signatures | ICSF | 📋 spec |
| §11 | **Relay** | Cluster state + shared state + broadcast | XCF | 📋 spec |
| §12 | **Warden** | Crash recovery + policy ops + escalation | ARM+SysAuto | 📋 spec |
| §13 | **Pulse** | MACS self-health + startup consistency | HC | 📋 spec |

## Implementation Repos

| § | Repository | Tests |
|:--:|-----------|:-----:|
| §2 | [macs-regulator-go](https://github.com/deeparchi-ai/macs-regulator-go) | 34 |
| §3 | [macs-sanctum-go](https://github.com/deeparchi-ai/macs-sanctum-go) | 13 |
| §3b | [macs-loom-go](https://github.com/deeparchi-ai/macs-loom-go) | 12 |
| §4 | [a2a-go PR #377](https://github.com/a2aproject/a2a-go/pull/377) + [mcp-audit-go](https://github.com/deeparchi-ai/mcp-audit-go) + [chronicle-bridge-go](https://github.com/deeparchi-ai/macs-chronicle-bridge-go) + DUMP | 68 |
| §5 | [macs-xval-go](https://github.com/deeparchi-ai/macs-xval-go) | 11 |
| §6 | [jes-gate](integrations/jes-gate/) | 4 |
| §7 | [macs-curator-go](https://github.com/deeparchi-ai/macs-curator-go) | 13 |
| §8 | [macs-nexus-go](https://github.com/deeparchi-ai/macs-nexus-go) | 16 |

## Design Specs

| Spec | Covers |
|------|--------|
| [security-model.md](specs/security-model.md) | §3 Sanctum: tool profiles, param scopes, program pathing |
| [state-rollback.md](specs/state-rollback.md) | §3b Loom: causal-DAG rollback + two-phase commit |
| [xval-dfsms-vtam.md](specs/xval-dfsms-vtam.md) | §5 XVal · §7 Curator · §8 Nexus (pre-rename) |
| [trace-bridge/spec.md](trace-bridge/spec.md) | §4 Chronicle: A2A↔MCP trace context bridge |

## Related

- [MAEA Framework](https://github.com/deeparchi-ai/MAEA-Framework) — canonical spec
- [macs-regulator-go](https://github.com/deeparchi-ai/macs-regulator-go) — resource scheduler
- [a2a-go](https://github.com/a2aproject/a2a-go) — A2A protocol Go SDK (+ Chronicle trace)

---

> *DeepArchi Team · 2026-07-18 · MIT License*
