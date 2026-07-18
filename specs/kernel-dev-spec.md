# MACS Kernel — Development Specification

> **Implementation target**: dev team
> **Reviewer / Acceptor**: 邝谧 (Hermes Agent)
> **Repo**: `deeparchi-ai/macs-kernel-go`

## Architecture

Kernel is the BCP-equivalent infrastructure layer. All 14 MACS subsystems `import` it. It is NOT a subsystem — no § number. It is 0-layer shared foundation.

```
        ┌──────────────────────────────┐
        │         macs-kernel-go        │
        │                              │
        │  Arbiter  Brake  Audit       │
        │  Trace    Lock                │
        └──────────┬───────────────────┘
                   │ import
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
  Regulator     Sanctum       Chronicle
     │             │             │
     └─────────────┼─────────────┘
                   ▼
              Agent Context
```

## z/OS BCP Mapping

| Kernel Component | z/OS BCP | Role | Why |
|-----------------|----------|------|-----|
| `arbiter.go` | Dispatcher | Unified admission | Replaces scattered Regulator+Sanctum logic |
| `brake.go` | SVC Handler | Circuit breaker | Any subsystem call can fail → unified protection |
| `audit.go` | SRB | Audit hook registry | Chronicle subscribes to kernel events |
| `trace.go` | W3C traceparent | Trace context propagation | Every span roots here |
| `lock.go` | Lock Manager | Concurrency control | Agent state r/w guard, deadlock detection |

## File Structure

```
pkg/kernel/
├── arbiter.go        # Admission: budget check + security check → allow/deny
├── brake.go          # CircuitBreaker: closed→open→half-open lifecycle
├── audit.go          # Hook registry: subsystems register hooks, publish events
├── trace.go          # W3C traceparent: Inject/Extract, SpanID generation
├── lock.go           # Concurrency: RWMutex per agent LU name
├── types.go          # Shared types: AdmissionRequest, AuditEvent, SpanContext
└── kernel_test.go    # All tests (15+)
```

---

## Component Specs

### 1. Arbiter (`arbiter.go`, ~80 lines)

**Purpose**: Single-entry admission gate. Merges Regulator's budget check + Sanctum's security check.

```go
package kernel

type AdmissionRequest struct {
    AgentLU       string
    TokenBudget   TokenBudget     // from Regulator
    SecurityLevel int             // from Sanctum
    CallType      string          // "llm_call", "tool_call", "agent_delegate"
}

type AdmissionResult struct {
    Allowed      bool
    Reason       string           // why denied, empty if allowed
    Importance   int              // 0=critical, 1=high, 2=standard
    DegradeTo    string           // if token budget forcing model downgrade
}

type TokenBudget struct {
    Level  string  // "green", "yellow", "red", "black"
    Limit  int
    Used   int
}

type BudgetChecker func(agent string) TokenBudget
type SecurityChecker func(agent string) int

func NewArbiter(bc BudgetChecker, sc SecurityChecker) *Arbiter
func (a *Arbiter) Admit(req AdmissionRequest) AdmissionResult
```

**Admission logic**:

| Budget | Security L1 | Security L2 | Security L3 | Result |
|:------:|:--:|:--:|:--:|------|
| green | ✓ | ✓ | ✓ | Allow |
| yellow | ✓ | ✓ | ✓ | Allow + suggest smaller model |
| red | ✓ | ✓ | ✗ | Allow L1/L2 only + degrade model |
| red | ✗ | ✗ | ✗ | Deny + "budget red, security insufficient" |
| black | ✓ | — | — | Allow importance-1 only |
| black | ✗ | — | — | Deny |

### 2. Brake (`brake.go`, ~90 lines)

**Purpose**: Circuit breaker for any subsystem call. Three states: closed → open → half-open.

```go
package kernel

type CBState int
const (
    CBClosed    CBState = iota  // normal operation
    CBOpen                      // failing, reject all calls
    CBHalfOpen                  // testing recovery
)

type CBOptions struct {
    MaxFailures    int           // trips after N consecutive failures
    ResetTimeout   time.Duration // how long to stay open before half-open
    HalfOpenMax    int           // max calls in half-open before deciding
}

type CircuitBreaker struct { ... }

func NewCircuitBreaker(name string, opts CBOptions) *CircuitBreaker
func (cb *CircuitBreaker) State() CBState
func (cb *CircuitBreaker) Execute(fn func() error) error
func (cb *CircuitBreaker) Success()
func (cb *CircuitBreaker) Failure()
func (cb *CircuitBreaker) TripReason() string
```

**State transitions**:

```
CLOSED ──(N failures)──► OPEN ──(timeout)──► HALF-OPEN
   ▲                                              │
   │                          ┌───────────────────┤
   │                          ▼                   ▼
   └────────(success)──  CLOSED       OPEN ◄──(failure)
```

### 3. Audit (`audit.go`, ~70 lines)

**Purpose**: Hook registry. Subsystems register callback hooks. When an event fires, all registered hooks for that event type are called.

```go
package kernel

type AuditEvent struct {
    Type      string    // "agent.call", "model.error", "budget.threshold"
    AgentLU   string
    Timestamp time.Time
    Data      map[string]interface{}
    TraceID   string
}

type AuditHook func(AuditEvent)

type AuditHub struct { ... }

func NewAuditHub() *AuditHub
func (h *AuditHub) On(eventType string, hook AuditHook)
func (h *AuditHub) Emit(event AuditEvent) int  // returns count of hooks called
func (h *AuditHub) Remove(eventType string, hook AuditHook)
```

### 4. Trace (`trace.go`, ~60 lines)

**Purpose**: W3C traceparent header inject/extract. Generates span IDs.

```go
package kernel

type SpanContext struct {
    TraceID    string  // 32 hex chars
    SpanID     string  // 16 hex chars
    TraceFlags string  // "01" = sampled
}

func NewSpanContext() SpanContext                    // new trace
func NewChildSpan(parent SpanContext) SpanContext    // child span
func InjectTraceparent(ctx SpanContext) string       // → "00-{trace}-{span}-01"
func ExtractTraceparent(header string) (SpanContext, error)
```

### 5. Lock (`lock.go`, ~60 lines)

**Purpose**: Per-agent read/write lock. Prevents concurrent conflicting access to agent state. Deadlock detection via timeout.

```go
package kernel

type AgentLock struct { ... }

func NewAgentLock() *AgentLock
func (al *AgentLock) AcquireRead(luName string, timeout time.Duration) error
func (al *AgentLock) AcquireWrite(luName string, timeout time.Duration) error
func (al *AgentLock) ReleaseRead(luName string)
func (al *AgentLock) ReleaseWrite(luName string)
func (al *AgentLock) HeldLocks() []string  // for diagnostics
```

---

## Testing

**Minimum 15 tests**:

| # | Test | Component |
|:--:|------|:--:|
| 1 | green budget + L1 → allow | Arbiter |
| 2 | yellow budget + L1 → allow + degrade | Arbiter |
| 3 | red budget + L3 only → deny | Arbiter |
| 4 | black budget + importance-1 → allow | Arbiter |
| 5 | black budget + importance-2 → deny | Arbiter |
| 6 | closed → open after N failures | Brake |
| 7 | open → half-open after timeout | Brake |
| 8 | half-open + success → closed | Brake |
| 9 | half-open + failure → open | Brake |
| 10 | emit event → all registered hooks called | Audit |
| 11 | remove hook → not called | Audit |
| 12 | traceparent inject/extract round-trip | Trace |
| 13 | child span from parent | Trace |
| 14 | read lock blocks write lock | Lock |
| 15 | write lock blocks read lock | Lock |
| 16 | lock timeout returns error | Lock |
| 17 | concurrent reads allowed | Lock |

---

## Go Setup

```bash
go mod init github.com/deeparchi-ai/macs-kernel-go
GOPROXY=https://goproxy.cn,direct
```

## Deliverables

1. [ ] `go.mod` + `go.sum`
2. [ ] `LICENSE` (MIT)
3. [ ] `README.md`
4. [ ] `pkg/kernel/` — all 7 files
5. [ ] `go test ./...` — 17+ tests pass
6. [ ] Commit: `feat(kernel): v0.1 — BCP-equivalent infrastructure (Arbiter+Brake+Audit+Trace+Lock)`
7. [ ] Push to `deeparchi-ai/macs-kernel-go` main

## Acceptance Gate

Hermes Agent will run `macs/specs/kernel-acceptance-tests.md`.
