# MACS §6 Cadence — Design Document

> IBM lineage: **JES2** (Job Entry Subsystem) + **SDSF** (Spool Display and Search Facility)

## 1. Design Decisions

### 1.1 Single-Image Scope

| Mechanism | z/OS Mechanism | MACS Design | Rationale |
|-----------|:---:|------|------|
| Job queue | JES2 SPOOL (DASD) | Kernel `checkpoint.go` + in-memory priority heap | Single-image — no MAS needed |
| Initiator assignment | JES2 INIT | `InitiatorPool` — N goroutines polling queue | No WLM-managed initiators; Regulator sets priority |
| Output management | SDSF SPOOL | `JobOutput` store + Console §14 query | Console plays SDSF role |
| Failure recovery | JES2 warm start | Kernel `checkpoint.go` replay | Checkpoint persists claim state |
| Job chaining | JCL COND= | `Job.NextJobs` DAG — trigger on complete | Event-driven via Relay §11 |

**Key simplification vs z/OS:** No JES2 MAS (multi-access spool) because MACS is single-image. No NJE (network job entry) because batch jobs run on the same MACS instance.

### 1.2 Why Not a Generic Task Queue (Celery/Sidekiq/RabbitMQ)?

| Concern | Generic Queue | MACS Cadence |
|---------|:---:|------|
| Importance class integration | External | Native — Regulator §2 sets priority class |
| Agent context preservation | None | Kernel `subpool.go` — job holds agent resources |
| Audit chain | App-level | Kernel `trace.go` — embedded in SMF-equivalent stream |
| Job chaining | Callback hell | Declarative `NextJobs` DAG |
| Console integration | Separate dashboard | Native Console §14 `job list/submit/cancel` |

## 2. Architecture

```
  ┌─────────────────────────────────────────────┐
  │                  Cadence                      │
  │                                               │
  │  JobSubmit() ──► JobQueue (priority heap)     │
  │                      │                        │
  │              ┌───────┼───────┐                │
  │              ▼       ▼       ▼                │
  │         Initiator  Init   Init  (N goroutines)│
  │              │       │       │                │
  │              ▼       ▼       ▼                │
  │         JobOutput store ◄── Console §14       │
  │                                               │
  │  Integration:                                  │
  │  ┌─ kernel/shared/checkpoint → JobClaim       │
  │  ├─ kernel/shared/registry   → AgentState     │
  │  ├─ kernel/shared/subpool    → Agent subpool  │
  │  └─ kernel/shared/dispatch   → NotifyConsole  │
  └─────────────────────────────────────────────┘
```

## 3. z/OS Mapping

| z/OS | MACS Cadence | Notes |
|------|------|------|
| JES2 INPUT queue | `JobQueue` — priority heap, max depth from PARMLIB | Single queue, no SYSOUT class |
| JES2 INIT (initiator) | `Initiator` goroutine — gets highest-priority job, executes | No WLM-managed initiator count |
| JES2 Checkpoint | `kernel/shared/checkpoint.go` | Shared with Kernel, not Cadence-owned |
| SDSF ST (status) | Console §14 `job list --status=running` | Console is the SDSF panel |
| SDSF ? (output browse) | Console §14 `job output <id>` | Output stored as string |
| JCL COND= | `Job.NextJobs` — DAG edges | Simple trigger; no RC comparison |
| $HASP373 (job ended) | `Relay.Publish("job.complete")` | Event-driven notification |
| JES2 warm start | `checkpoint.Replay()` on startup | Recovers incomplete jobs |

## 4. PARMLIB

```yaml
# etc/macs-parmlib/CADENCE.yaml
cadence:
  initiators: 8
  max_queue_depth: 256
  dispatch_interval_ms: 100
```

## 5. Integration Surface

| Imported by Cadence | Purpose |
|------|------|
| `kernel/shared.Checkpoint` | Atomic job claiming, completion, failure |
| `kernel/shared.Registry` | Agent lookups and state queries |
| `kernel/shared.Subpool` | Agent resource group lifecycle |
| `kernel/shared.DispatchTable` | Console + Chronicle notifications |

| Consumed from Cadence | By | Purpose |
|------|------|------|
| `JobQueue.Submit()` | Console §14, Cron, A2A | Job submission |
| `JobOutput.Get(id)` | Console §14 | Result retrieval |
| Event `job.complete` | Relay §11 | Job chaining trigger |
| Event `job.failed` | Warden §12 | Crash escalation |
