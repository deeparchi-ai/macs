# MACS §13 — Pulse: Self-Health Monitoring & Startup Consistency

> **DeepArchi · 邝谧**
> *Working Draft v0.1 — Pre-implementation design for the self-health subsystem.*
> IBM lineage: **z/OS Health Checker**

## Abstract

Pulse continuously monitors MACS subsystem health through registered health checks, computes an aggregate health status (healthy → degraded → impaired → down), and propagates dependency-aware degradation through a dependency graph. It ensures that all subsystems are operational at startup and remain healthy throughout the system lifetime.

## Problem

MACS consists of 14 subsystems with complex inter-dependencies. If DFSMS (§7) fails, VTAM (§8) may continue operating but with degraded functionality (no context recall). If the Kernel fails, everything is down. Without a centralized health monitor: (a) individual subsystems detect their own failures but no one computes the aggregate picture, (b) dependency chains are invisible — a failure in a leaf subsystem should degrade its dependents, not trigger false "everything is down" alerts, and (c) startup ordering is ad-hoc with no consistency check that all required subsystems are ready before accepting work.

Existing health check solutions (Kubernetes liveness/readiness probes, Nagios checks) are designed for infrastructure — "is the process running?" — not for subsystem-level health: "is DFSMS able to compress and recall context?" Pulse fills this gap with subsystem-aware health checks, dependency-graph propagation, and aggregate status computation.

The dependency graph is the critical differentiator. When Pulse reports "degraded," it can trace the root cause: "VTAM is degraded because its dependency DFSMS is impaired." This prevents the classic monitoring failure where every dependent subsystem fires alerts simultaneously, flooding operators with noise instead of pointing to the root cause.

## Mainframe Analogy

IBM **z/OS Health Checker** continuously monitors the health of z/OS subsystems and middleware components against best-practice checks defined by IBM and the customer. It runs checks on a configurable interval, tracks consecutive failures, and raises exceptions when thresholds are exceeded. The Health Checker also supports startup checks — verifying that prerequisites are met before a component becomes operational. Pulse adopts this model: `Checker` mirrors the Health Checker's check registration and execution; `DependencyGraph` mirrors the Health Checker's exception correlation (tracing a failure to its root cause); startup consistency mirrors the Health Checker's initialization checks.

## Data Model

```go
// HealthStatus represents the aggregate health of the MACS system.
type HealthStatus int

const (
    StatusHealthy   HealthStatus = iota // all checks passing
    StatusDegraded                      // non-critical subsystem(s) down
    StatusImpaired                      // critical subsystem down
    StatusDown                          // kernel unresponsive
)

// HealthCheck is a single health probe.
type HealthCheck struct {
    Name                 string
    Run                  func() error      // returns nil if healthy
    Interval             time.Duration
    IsCritical           bool               // true = failure causes Impaired or Down
    LastResult           error
    LastRun              time.Time
    ConsecutiveFailures  int
    MaxConsecutiveFails  int                // trigger after this many (default 3)
}

// Checker registers and runs health checks.
type Checker struct {
    mu     sync.RWMutex
    checks map[string]*HealthCheck
}

// DependencyGraph tracks which subsystems depend on which.
type DependencyGraph struct {
    mu   sync.RWMutex
    deps map[string][]string // parent → children
}
```

**Key methods:**

**Checker:** `Register(check *HealthCheck)`, `RunAll() map[string]error`, `Status() HealthStatus`, `FailedChecks() []*HealthCheck`

**DependencyGraph:** `AddDependency(parent, child string)`, `Propagate(failed string) map[string]string`, `Dependencies(parent string) []string`

## Algorithm

### 1. Health Check Registration
```
On startup, each MACS subsystem registers its health check:
  - Kernel:    Check{Name: "kernel-liveness", IsCritical: true}
  - DFSMS §7:  Check{Name: "dfsms-recall", IsCritical: false, Run: testRecall()}
  - VTAM §8:   Check{Name: "vtam-routing", IsCritical: true, Run: testRoute()}
  - Gauge §9:  Check{Name: "gauge-collection", IsCritical: false, Run: testCollect()}
  - Seal §10:  Check{Name: "seal-registry", IsCritical: true, Run: testLookup()}
  - Relay §11: Check{Name: "relay-broadcast", IsCritical: true, Run: testPubSub()}
  - Warden §12:Check{Name: "warden-detector", IsCritical: true, Run: testDetect()}
  - Pulse §13: Check{Name: "pulse-self", IsCritical: false, Run: testSelf()}
```

### 2. Periodic Health Evaluation
```
Every 30s (configurable):
  1. Checker.RunAll() — execute every registered check
  2. For each check: if Run() returns error → ConsecutiveFailures++
                    if Run() returns nil  → ConsecutiveFailures = 0
  3. Checker.Status() determines aggregate:
     - Any critical check with ConsecutiveFailures >= MaxConsecutiveFails → Impaired
     - Any non-critical check with failures → Degraded
     - All checks passing → Healthy
  4. If Kernel check fails → StatusDown (overrides all others)
  5. Emit "pulse.status" event via Relay §11 with current HealthStatus
  6. For each failed check, run DependencyGraph.Propagate(failedCheck) → affected list
```

### 3. Status Computation Logic
```
Status() HealthStatus:
  input: all checks, each with LastResult, ConsecutiveFailures, MaxConsecutiveFails, IsCritical

  if no checks registered → StatusHealthy (empty system is healthy by vacuity)

  for each check:
    if LastResult != nil AND ConsecutiveFailures >= MaxConsecutiveFails:
      if IsCritical → anyCriticalDown = true
      else          → anyNonCriticalDown = true

  if anyCriticalDown → StatusImpaired
  if anyNonCriticalDown → StatusDegraded
  return StatusHealthy
```

### 4. Dependency Graph Propagation
```
Given: DFSMS is impaired

Propagate("dfsms-7"):
  1. Start queue = ["dfsms-7"]
  2. Dequeue "dfsms-7"
  3. For each (parent, children) in deps:
       If "dfsms-7" is in children:
         affected[parent] = "dependency dfsms-7 is unhealthy"
         Enqueue parent
  4. Dequeue "vtam-8" (depends on dfsms-7)
  5. Check if any other parent depends on "vtam-8":
       Console §14 depends on VTAM → affected["console-14"] = "dependency vtam-8 is unhealthy"
  6. Queue exhausted → return affected map

Result: {vtam-8: "dependency dfsms-7 is unhealthy", console-14: "dependency vtam-8 is unhealthy"}
```

### 5. Startup Consistency Check
```
On MACS boot:
  1. All subsystems register their health checks
  2. Pulse runs Checker.RunAll() once before accepting any requests
  3. If any critical check fails → MACS refuses to start, reports which checks failed
  4. If only non-critical checks fail → MACS starts in StatusDegraded
  5. Startup gate prevents cascading failures from partially-initialized subsystems
```

## Integration Points

| Consumed by Pulse | Purpose |
|------|------|
| All MACS subsystems | Register health checks at startup |
| Kernel | Kernel liveness is the root health check |
| Relay §11 | Publish health status events, receive subsystem liveness events |

| Consumed from Pulse | By | Purpose |
|------|------|------|
| `Checker.Status()` | Console §14 | Dashboard health indicator (green/yellow/red) |
| `Checker.FailedChecks()` | Console §14 | Drill-down into failing checks |
| `DependencyGraph.Propagate()` | Console §14 | Root-cause analysis display |
| `pulse.status` event | Warden §12 | Trigger recovery when health degrades |
| `pulse.status` event | Regulator §2 | Adjust priority class based on system health |
| `StatusDown` detection | Kernel | Graceful shutdown when system is non-recoverable |

## Implementation Plan

| Phase | Lines | Scope |
|------|:-----:|------|
| Phase 1 | ~100 | HealthCheck, HealthStatus, Checker (Register/RunAll/Status/FailedChecks) |
| Phase 2 | ~80 | DependencyGraph (AddDependency/Propagate/Dependencies), BFS propagation |
| Phase 3 | ~60 | Periodic check scheduling goroutine, check interval management |
| Phase 4 | ~60 | Startup consistency gate, pre-flight check integration |
| Phase 5 | ~50 | Relay event integration (pulse.status), Warden policy integration |
| **Total** | **~350** | |

## Non-Goals

- **External service monitoring** — Pulse monitors MACS subsystems only. External vendor API health is Gauge §9's responsibility (fed into Pulse via health check dependencies).
- **Synthetic transaction monitoring** — End-to-end workflow testing ("run a full agent task and verify") is a Cadence §6 concern, not a health check. Pulse checks subsystem-level functions.
- **Remediation** — Pulse detects and reports health degradation. Recovery actions are Warden §12's domain. Pulse answers "what's wrong?"; Warden answers "what do we do about it?"
- **Distributed health consensus** — Pulse reports single-image health. Cross-node MACS cluster health aggregation requires Relay §11 coordination and is out of scope for v0.1.
- **Performance regression detection** — Pulse checks binary health (pass/fail). Gradual performance degradation detection is Gauge §9 territory.
