# MACS Reference Architecture — Quick Reference

Full specification: [MACS Governance Specification v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)
(MAEA Framework). Canonical source of truth.

## Fourteen Subsystems

| § | Name | IBM z/OS | Status | Artifacts |
|:--:|------|-----------|:------:|-----------|
| §2 | **Regulator** | WLM — Workload Manager | partial | [regulator-go](https://github.com/deeparchi-ai/macs-regulator-go) (34 tests) |
| §3 | **Sanctum** | RACF — Resource Access Control Facility | v0.1 | [sanctum-go](https://github.com/deeparchi-ai/macs-sanctum-go) (13 tests) |
| §3b | **Loom** | CICS Syncpoint | v0.1 | [loom-go](https://github.com/deeparchi-ai/macs-loom-go) (12 tests) |
| §4 | **Chronicle** | SMF — System Management Facilities | partial | [a2a-go #377](https://github.com/a2aproject/a2a-go/pull/377) (20) + [mcp-audit-go](https://github.com/deeparchi-ai/mcp-audit-go) (10) + [bridge](https://github.com/deeparchi-ai/macs-chronicle-bridge-go) (19) + DUMP (19) |
| §5 | **XVal** | *(agent-native)* | v0.2 tri | [xval-go](https://github.com/deeparchi-ai/macs-xval-go) (31 tests) |
| §6 | **Cadence** | JES2 — Job Entry Subsystem + SDSF | POC | jes-gate (4 scenarios) |
| §7 | **Curator** | DFSMS — Data Facility Storage Management Subsystem | v0.1 | [curator-go](https://github.com/deeparchi-ai/macs-curator-go) (13 tests) |
| §8 | **Nexus** | VTAM — Virtual Telecommunications Access Method | v0.1 | [nexus-go](https://github.com/deeparchi-ai/macs-nexus-go) (16 tests) |
| §9 | **Gauge** | RMF — Resource Measurement Facility + NetView | v0.1 | [gauge-go](https://github.com/deeparchi-ai/macs-gauge-go) (20 tests) |
| §10 | **Seal** | ICSF — Integrated Cryptographic Service Facility | v0.1 | [seal-go](https://github.com/deeparchi-ai/macs-seal-go) (19 tests) |
| §11 | **Relay** | XCF — Cross-system Coupling Facility | v0.1 | [relay-go](https://github.com/deeparchi-ai/macs-relay-go) (15 tests) |
| §12 | **Warden** | ARM — Automatic Restart Manager + System Automation | v0.1 | [warden-go](https://github.com/deeparchi-ai/macs-warden-go) (12 tests) |
| §13 | **Pulse** | Health Checker | v0.1 | [pulse-go](https://github.com/deeparchi-ai/macs-pulse-go) (10 tests) |
| §14 | **Console** | TSO — Time Sharing Option + ISPF — Interactive System Productivity Facility | v0.1 | [console-go](https://github.com/deeparchi-ai/macs-console-go) (36 tests) |

## Non-Goals

- Not a new runtime/platform; no cluster to operate.
- Does not capture raw internal objects — sanitized telemetry view only.
- Upstream plugin stays self-contained / zero-dependency for mergeability.

---

*DeepArchi · 深度架构 · 2026-07-18*
