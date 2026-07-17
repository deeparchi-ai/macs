# MACS §3 — Causal-DAG State & Rollback

## CICS Syncpoint for Multi-Agent Workflows

> **DeepArchi · 邝谧**  
> 2026-07-18 · Working Draft v0.1  
> Status: Design · Pre-implementation

---

## Abstract

Existing agent state management is linear: checkpoint → execute → checkpoint. If something fails, roll back to the last checkpoint and retry. This works for single-agent workflows but breaks for multi-agent DAGs where one orchestrator spawns N subagents in parallel.

CICS Syncpoint solved this for distributed transactions in 1975: coordinate multiple resource managers (VSAM, DB2, MQ) under a single Unit of Work (UOW), with two-phase commit and branch-level rollback. This specification ports Syncpoint semantics to agent workflows.

---

## 1. The Problem: Linear Rollback vs. Causal DAG

### 1.1 What Existing Systems Do

```
Agent A: step1 → step2 → step3 ──FAIL──→ rollback to step2 checkpoint → retry step3
```

This is sufficient for one agent. But multi-agent workflows are DAGs:

```
                    ┌→ Agent B: b1 → b2 ✓
Orchestrator ───────┤
                    ├→ Agent C: c1 ──FAIL──
                    │
                    └→ Agent D: d1 → d2 → d3 ✓
```

If Agent C fails:
- **Linear rollback would undo everything** — including Agent B and Agent D's successful work
- **Selective rollback should undo only C's branch** — preserving B and D
- But C's failure might **contaminate a shared resource** that B and D also depend on

### 1.2 The Causal DAG

A multi-agent workflow is a **directed acyclic graph** where:

- **Nodes** = agent decisions + tool calls
- **Edges** = data flow + causal dependency
- **Branches** = parallel sub-workflows from a fork point

When a node fails, the rollback must traverse the **reverse causal edges** — undoing only the nodes that causally depend on the failed node.

---

## 2. Unit of Work (UOW)

### 2.1 Definition

A UOW is the transactional boundary: all-or-nothing across all participating agents.

```go
type UnitOfWork struct {
    UOWID       string            // unique, cross-workflow
    PrincipalID string            // who initiated
    CreatedAt   time.Time
    Status      UOWStatus         // active | committing | committed | backing_out | aborted
    RootTaskID  string            // the orchestrator's initial task
    
    // Participants register their recoverable actions
    Participants []Participant
    
    // The causal DAG
    Graph       *CausalDAG
}

type Participant struct {
    AgentID     string
    ResourceID  string            // what this agent modified
    PrepareFn   string            // callback: can we commit?
    CommitFn    string            // callback: apply
    RollbackFn  string            // callback: undo
}
```

### 2.2 Resource Types

Not all actions need rollback. MACS classifies resources:

| Resource Type | Rollback? | Example |
|:---|:---:|---|
| **Ephemeral** | No | LLM think, temporary scratch |
| **Idempotent** | No | Read-only, GET, search |
| **Recoverable** | Yes | File write, database insert, email send |
| **Irreversible** | Compensate | Payment, API call with side effects, tweet |

For irreversible resources, "rollback" means executing a **compensating action** — not undoing the original, but performing an equivalent reversal (refund, delete tweet, etc.).

---

## 3. Two-Phase Commit Protocol

### 3.1 Phase 1: Prepare

```
Orchestrator → All Participants: "Can you commit?"
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
    Agent B: YES         Agent C: YES         Agent D: NO (budget exhausted)
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ▼
                    Orchestrator decides: ROLLBACK ALL
```

### 3.2 Phase 2: Commit / Rollback

```
If all YES → COMMIT: each participant applies its changes
If any NO  → ROLLBACK: each participant calls RollbackFn (or CompensateFn)
```

### 3.3 Timeout

If a participant doesn't respond within `PrepareTimeout`, treat as NO → rollback.

---

## 4. Causal DAG Rollback

### 4.1 The Algorithm

When node N fails, the rollback set is:

```
RollbackSet(N) = {N} ∪ {M | M is reachable from N via reverse causal edges AND M is in the same UOW}
```

In English: undo N and everything that depends on N, but don't touch unrelated branches.

### 4.2 Example

```
                    ┌→ Agent B: [b1:search] → [b2:write_file report_b.md] ✓
Orchestrator ───────┤
                    ├→ Agent C: [c1:search] → [c2:FAIL]                    ✗
                    │
                    └→ Agent D: [d1:read c1_result] → [d2:write_file report_d.md]
```

Agent C fails at c2. The rollback set:

- **c2**: undo (if recoverable)
- **c1**: no rollback needed (read-only)
- **d1**: depends on c1's result — if c1's result was corrupted by c2, d1 is contaminated
- **d2**: depends on d1 — cascade

Agent B is **not** in the rollback set because it has no causal dependency on C.

### 4.3 Contamination Detection

Contamination happens when a failed node's data flows to another branch:

```go
func (dag *CausalDAG) ContaminationSources(failedNode string) []string {
    // Walk forward from failedNode through data-flow edges
    // Any node that consumed output from failedNode's sub-DAG is contaminated
    return contaminated
}
```

---

## 5. Checkpoint Model

### 5.1 Fork Point Snapshots

Each fork point in the DAG takes a snapshot. When a branch fails, roll back to the fork point and replay only the surviving branches:

```
Fork point at orchestrator:
  ├── Branch B: b1 → b2 ✓  (snapshot: B done, output = report_b.md)
  ├── Branch C: c1 → c2 ✗  (rollback to fork)
  └── Branch D: d1 → d2 ✓  (snapshot: D done, output = report_d.md)
  
After C's rollback:
  ├── Branch B: preserved from snapshot
  ├── Branch C: retry from fork point (new attempt)
  └── Branch D: preserved from snapshot
```

### 5.2 Incremental vs. Full Snapshots

- **Fork point**: full snapshot (state before branching)
- **Branch progress**: incremental (only the delta since fork)
- **Failed node**: no snapshot (already failed)

---

## 6. Agent Protocol Extensions

### 6.1 Enlist

An agent joins a UOW by calling `Enlist`:

```go
func (a *Agent) Enlist(uow *UnitOfWork, resources []ResourceID) error
```

This registers the agent as a participant and declares which resources it intends to modify.

### 6.2 Prepare Callback

Called by the UOW coordinator during Phase 1:

```go
func (a *Agent) Prepare(ctx context.Context) (PrepareResult, error)

type PrepareResult struct {
    CanCommit   bool
    Reason      string   // if no: why
    Compensate  bool     // if no: can we compensate instead of rollback?
}
```

### 6.3 Commit / Rollback Callbacks

```go
func (a *Agent) Commit(ctx context.Context) error
func (a *Agent) Rollback(ctx context.Context) error
```

### 6.4 In Practice: Hermes Adapter

For Hermes agents, the UOW is implicit — the orchestrator's session is the UOW boundary. Resources are tracked automatically:

- File writes → tracked by path + checksum before/after
- Tool calls → tracked by tool name + params + result hash
- Subagent spawns → tracked by subagent session ID

---

## 7. Limits (Explicit Non-Goals)

### 7.1 Not Serializable

MACS does not guarantee serializable isolation across agents. Two concurrent agents can read stale data. This is a deliberate trade-off — full serializability would require distributed locking, which violates the "fail-open overlay" principle.

### 7.2 Not ACID

MACS provides **atomicity** (all-or-nothing per UOW) and **durability** (checkpoints survive crashes). It does NOT provide:
- **Consistency**: agents can produce inconsistent intermediate states
- **Isolation**: concurrent agents can interfere

### 7.3 No Cross-Organization Rollback

If Agent B at Company X fails, MACS cannot roll back Agent C at Company Y. Cross-org commitments require legal contracts, not protocols.

---

## 8. License

| Dependency | License | Copyleft | Commercial OK |
|------------|---------|:--------:|:-------------:|
| stdlib only | Go BSD | No | ✅ |

---

## 9. Implementation Plan

| Phase | Deliverable | Lines |
|:-----:|------------|:-----:|
| v0.1 | `UnitOfWork` + `Participant` + `ResourceType` data types | ~100 |
| v0.2 | `CausalDAG` with rollback set computation | ~150 |
| v0.3 | Two-phase commit coordinator | ~150 |
| v0.4 | Fork-point snapshot + branch replay | ~100 |
| v0.5 | Hermes adapter: track file writes, tool calls, subagents | ~150 |

Total: ~650 lines Go.

---

*DeepArchi · 深度架构*
