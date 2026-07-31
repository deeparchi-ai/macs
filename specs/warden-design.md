# MACS §12 — Warden: Crash Recovery & Policy-Driven Operations

> **DeepArchi · 邝谧**
> *Working Draft v0.1 — Pre-implementation design for the recovery and operations subsystem.*
> IBM lineage: **ARM** (Automatic Restart Manager) + **System Automation**

## Abstract

Warden is the MACS operational control plane that detects agent crashes, enforces declarative policies against real-time state, executes automated recovery plans, and escalates unresolved incidents through a severity chain (informational → warning → auto-mitigate → human escalation). It combines ARM's crash-restart semantics with System Automation's policy-driven operations.

## Problem

Multi-agent systems fail in complex ways: agent crashes, crash-loops (restart → crash → restart), vendor degradation, and latent policy violations. Without automated detection and recovery: (a) a crashed agent goes unnoticed until its dependents time out (cascade failure), (b) a crash-looping agent wastes resources restarting indefinitely, and (c) policy violations (e.g., cost overruns, excessive latency) are discovered retroactively by humans rather than mitigated in real time.

Existing process supervisors (systemd, supervisord) restart dead processes but lack agent-semantic awareness: they don't know that "xval-claude crashed 3 times in 5 minutes" is a crash-loop requiring escalation, not another restart attempt. Monitoring tools (Prometheus Alertmanager) evaluate threshold rules but don't execute recovery plans — they page humans. Warden bridges this gap: it detects agent-level failures, evaluates declarative policies against current state, and executes multi-tier recovery actions before escalating.

The policy engine is particularly important because it centralizes operational rules that would otherwise be scattered across agent code. A rule like "if API error rate exceeds 20% for 5 minutes, switch to backup vendor" is expressed declaratively in the policy DSL and enforced uniformly — rather than being reimplemented by every agent that calls that vendor.

## Mainframe Analogy

IBM z/OS **ARM (Automatic Restart Manager)** detects when a started task or subsystem fails and automatically restarts it according to a restart policy (restart count, interval, escalation). **System Automation** extends this with policy-based automation — operators declare desired states and automation enforces them through a manager/agent architecture. Warden combines both: the `CrashDetector` mirrors ARM's heartbeat monitoring and crash-loop detection; the `PolicyEngine` mirrors System Automation's declarative policy evaluation; the `EscalationChain` mirrors the multi-tier escalation model (informational → warning → auto-mitigate → human).

## Data Model

```go
// ── Escalation ──

type EscalationLevel int
const (
    EscL0Informational  EscalationLevel = iota // log only
    EscL1Warning                               // notify owner
    EscL2ActionRequired                        // auto-mitigate
    EscL3Critical                              // mitigate + escalate to human
)

type EscalationChain struct {
    Levels       []EscalationLevel
    Reason       string
    CurrentLevel int // -1 = not started
}

// ── Crash Detection ──

type CrashDetector struct {
    mu         sync.RWMutex
    heartbeats map[string]time.Time     // agent name → last heartbeat
    failures   map[string][]time.Time   // agent name → recent failure times
    window     time.Duration             // crash-loop detection window
}

// ── Policy Engine ──

type Policy struct {
    Name            string
    Condition       string // DSL: "agent.failures(5m) >= 3"
    Actions         []string
    EscalationLevel EscalationLevel
}

type PolicyEngine struct {
    policies []Policy
}
```

**Key methods:**

**CrashDetector:** `MarkHeartbeat(agent)`, `Check(agent, timeout) bool`, `RecordFailure(agent) bool` (returns crash-loop detected), `ActiveFailures(agent) int`

**PolicyEngine:** `AddPolicy(p Policy)`, `Evaluate(state map[string]interface{}) []Policy`, `Execute(policy Policy) []string`

**EscalationChain:** `Escalate() EscalationLevel`, `Current() EscalationLevel`, `IsAtMax() bool`

## Algorithm

### 1. Crash Detection with Loop Prevention
```
Step 1: Each agent sends heartbeat every 5s → CrashDetector.MarkHeartbeat(agent)
Step 2: Detector goroutine: every 10s, Check(agent, 15s timeout) for each registered agent
Step 3: If Check returns true (no heartbeat in 15s) → agent has crashed
Step 4: RecordFailure(agent) — adds timestamp to failures[agent], prunes old entries
Step 5: If RecordFailure returns true (3+ failures in window) → crash-loop detected
Step 6: Crash-loop: escalate to L3 (critical — human intervention needed)
Step 7: Non-loop crash: attempt restart, escalate through chain on repeated failure
```

### 2. Policy Evaluation
```
Condition DSL grammar:
  "agent.failures(<duration>) <op> <number>"     e.g., "agent.failures(5m) >= 3"
  "gauge.latency.p95 <op> <number>"              e.g., "gauge.latency.p95 > 5000"
  "gauge.vendor.health <op> <number>"             e.g., "gauge.vendor.health < 0.8"
  "regulator.level == <string>"                   e.g., "regulator.level == RED"
  "regulator.token.pct <op> <number>"             e.g., "regulator.token.pct > 0.9"

Evaluate(state map[string]interface{}) []Policy:
  1. For each registered policy:
     a. Parse condition into <metric, op, threshold>
     b. Look up metric in state map
     c. If string metric: compare with == or !=
     d. If numeric metric (int or float64): compare with >=, >, <=, <, ==, !=
     e. If condition matches → add to triggered list
  2. Return all triggered policies (may be multiple)
```

### 3. Recovery Execution Flow
```
Trigger: CrashDetector detects agent crash
  ↓
1. PolicyEngine.Evaluate(state) → finds policy "crash-restart"
2. Policy.Actions: ["restart agent", "notify console"]
3. PolicyEngine.Execute(policy) → runs each action in sequence
4. If restart succeeds → emit "agent.recovered" event, EscL0 log only
5. If restart fails → EscalationChain.Escalate() → L2 (auto-mitigate: switch to backup)
6. If backup also fails → EscalationChain.Escalate() → L3 (critical: escalate to human via Console §14)
```

### 4. Crash-Loop Escalation Example
```
Time 0s:  Agent X crashes → RecordFailure → failures=1 → restart
Time 30s: Agent X crashes → RecordFailure → failures=2 → restart
Time 60s: Agent X crashes → RecordFailure → failures=3 → crash-loop detected!
          → EscalationChain skips L1, L2 → goes directly to L3
          → Action: "stop restart attempts, notify human, quarantine agent"
          → Emit "agent.crash-loop" event → Console §14 displays alert
```

## Integration Points

| Consumed by Warden | Purpose |
|------|------|
| Relay §11 `Cluster.DetectStale()` | Input to crash detection (stale cluster members) |
| Relay §11 `Broadcast.Subscribe("agent.heartbeat")` | Heartbeat event stream |
| Gauge §9 `MetricRegistry.Aggregate()` | Performance data for policy conditions |
| Regulator §2 | Token budget and priority level for policy conditions |

| Consumed from Warden | By | Purpose |
|------|------|------|
| `CrashDetector.MarkHeartbeat()` | All agents | Heartbeat registration |
| `PolicyEngine.Evaluate()` | Warden's own control loop | Periodic policy evaluation |
| `agent.crash-loop` event | Relay §11 → Console §14 | Alert display |
| `agent.recovered` event | Relay §11 → Cadence §6 | Resume paused jobs |
| Recovery actions | Cadence §6 | Submit restart jobs |
| `EscL3Critical` escalation | Console §14 | Human-in-the-loop notification |

## Implementation Plan

| Phase | Lines | Scope |
|------|:-----:|------|
| Phase 1 | ~100 | EscalationLevel, EscalationChain (Escalate/Current/IsAtMax) |
| Phase 2 | ~120 | CrashDetector (MarkHeartbeat/Check/RecordFailure/ActiveFailures) |
| Phase 3 | ~100 | Policy, PolicyEngine (AddPolicy/Evaluate/matchCondition/Execute) |
| Phase 4 | ~80 | Recovery plan executor, Relay event integration |
| Phase 5 | ~60 | Crash-loop escalation workflow, human-in-the-loop integration |
| **Total** | **~460** | |

## Non-Goals

- **Process spawning/management** — Warden detects crashes and decides what to do; actual process restart is delegated to Cadence §6 (job submission) or the host OS.
- **Distributed consensus for policy state** — Policies are evaluated against local state snapshots. Cross-node policy consensus is a future concern.
- **Full policy language** — The condition DSL handles simple `<metric> <op> <value>` expressions. Complex predicates (AND/OR, nested conditions) are out of scope for v0.1.
- **Runbook automation** — Warden executes recovery actions; authoring and versioning runbooks is a Console §14 concern.
- **Predictive failure detection** — Warden detects actual failures (heartbeat loss, threshold breach). ML-based anomaly prediction is out of scope.
