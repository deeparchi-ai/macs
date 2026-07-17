# MACS Reference Architecture — Quick Reference

Full specification: [MACS Governance Specification v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)
(MAEA Framework). Canonical source of truth.

## Thirteen Subsystems

| § | Name | z/OS | Status | Artifacts |
|:--:|------|:---:|:------:|-----------|
| §2 | **Regulator** | WLM | partial | [regulator-go](https://github.com/deeparchi-ai/macs-regulator-go) (34 tests) |
| §3 | **Sanctum** | RACF | v0.1 | [sanctum-go](https://github.com/deeparchi-ai/macs-sanctum-go) (13 tests) |
| §3b | **Loom** | CICS | v0.1 | [loom-go](https://github.com/deeparchi-ai/macs-loom-go) (12 tests) |
| §4 | **Chronicle** | SMF | partial | [a2a-go #377](https://github.com/a2aproject/a2a-go/pull/377) (20) + [mcp-audit-go](https://github.com/deeparchi-ai/mcp-audit-go) (10) + [bridge](https://github.com/deeparchi-ai/macs-chronicle-bridge-go) (19) + DUMP (19) |
| §5 | **XVal** | *(native)* | v0.1→tri | [xval-go](https://github.com/deeparchi-ai/macs-xval-go) (11 tests) |
| §6 | **Cadence** | JES2 | POC | jes-gate (4 scenarios) |
| §7 | **Curator** | DFSMS | v0.1 | [curator-go](https://github.com/deeparchi-ai/macs-curator-go) (13 tests) |
| §8 | **Nexus** | VTAM | v0.1 | [nexus-go](https://github.com/deeparchi-ai/macs-nexus-go) (16 tests) |
| §9 | **Gauge** | RMF | spec | — |
| §10 | **Seal** | ICSF | spec | — |
| §11 | **Relay** | XCF | spec | — |
| §12 | **Warden** | ARM | spec | — |
| §13 | **Pulse** | HC | spec | — |

## Non-Goals

- Not a new runtime/platform; no cluster to operate.
- Does not capture raw internal objects — sanitized telemetry view only.
- Upstream plugin stays self-contained / zero-dependency for mergeability.

---

*DeepArchi · 深度架构 · 2026-07-18*
