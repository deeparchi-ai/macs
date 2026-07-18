# MACS Kernel v0.2 — Integration Layer Design

> **Canonical reference**: [MACS Governance Spec v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)
> **Repo**: `deeparchi-ai/macs-kernel-go`

## Architecture

```
macs-kernel-go/pkg/kernel/          ← v0.1 ✅
├── arbiter.go        # Admission gate
├── brake.go          # Circuit breaker
├── audit.go          # Hook registry
├── trace.go          # W3C traceparent
├── lock.go           # Agent concurrency
├── types.go          # Shared types

macs-kernel-go/pkg/kernel/shared/   ← v0.2 NEW
├── registry.go       # CSA: shared in-process state
├── dispatch.go       # SVC Table: function dispatch
├── subpool.go        # GETMAIN: agent-scoped resource groups
├── checkpoint.go     # JES2 Checkpoint: job coordination state
├── parmlib.go        # PARMLIB: config loader
├── parmlib_test.go
├── types.go
└── shared_test.go
```

## z/OS → MACS Mapping (Single-System Integration)

| z/OS | MACS Component | In-Scope |
|------|------|:--:|
| CSA / ECSA | `registry.go` — in-process typed maps | v0.2 |
| SVC Table | `dispatch.go` — function pointer table | v0.2 |
| Control Blocks | structured linked data via Registry | v0.2 |
| ENQ / DEQ | `lock.go` (v0.1 ✅) | — |
| STOKEN | Agent LUName (v0.1 ✅) | — |
| SMF | `audit.go` (v0.1 ✅) | — |
| JES2 Checkpoint | `checkpoint.go` | v0.2 |
| PARMLIB | `parmlib.go` + `etc/macs-parmlib/` | v0.2 |
| GETMAIN Subpool | `subpool.go` | v0.2 |
| Console WTO | Console §14 (✅ separate repo) | — |
| PC / PT | Go native call (no mapping needed) | — |
| Linkage Stack | Go call stack (no mapping needed) | — |
| CDE / LLE | Go module resolution (no mapping needed) | — |

---

## Component Specs

### 1. Registry (`registry.go`, ~100 lines)

**z/OS lineage**: CSA/ECSA — Common Storage Area.

All subsystems share a single in-process `Registry`. No RPC, no channels —
direct memory access via typed maps. Subsystems read fields written by other
subsystems without importing each other.

```go
package shared

type AgentState struct {
    LUName       string
    TokenBudget  TokenBudget     // §2 Regulator writes, §9 Gauge reads
    TrustScore   float64         // §3 Sanctum writes, Kernel Arbiter reads
    Health       HealthStatus    // §13 Pulse writes, §14 Console reads
    Heartbeat    time.Time       // §12 Warden writes
    CrashCount   int             // §12 Warden writes
    ForkPoint    string          // §3b Loom writes, §12 Warden reads
    ContextHot   bool            // §7 Curator writes, Warden reads
    Identities   []IdentityRef   // §10 Seal writes
}

type Registry struct {
    mu     sync.RWMutex
    Agents map[string]*AgentState   // LUName → state
    CBs    map[string]*BrakeRef     // brake name → handle
    Jobs   map[string]*JobState     // job ID → state
}

func NewRegistry() *Registry
func (r *Registry) GetAgent(luName string) *AgentState     // read-snapshot pointer
func (r *Registry) UpdateAgent(luName string, fn func(*AgentState))  // atomic RMW
func (r *Registry) ListAgents(filter AgentFilter) []*AgentState
func (r *Registry) AgentCount() int
```

### 2. Dispatch Table (`dispatch.go`, ~50 lines)

**z/OS lineage**: SVC Table.

A function-pointer table. Subsystems register their handlers; consumers call
through the table without importing the providing package.

```go
package shared

type AdmitFunc func(AdmissionRequest) AdmissionResult
type AuditFunc func(AuditEvent)

type DispatchTable struct {
    Admit    AdmitFunc         // → Kernel Arbiter
    Emit     AuditFunc         // → Kernel AuditHub
    Status   func() string     // → Pulse
}

func NewDispatchTable() *DispatchTable
```

### 3. Subpool (`subpool.go`, ~50 lines)

**z/OS lineage**: GETMAIN Subpool. Group resources by lifecycle owner.
When an Agent goes offline, all its resources are released in one shot —
no GC needed, no dangling references.

```go
package shared

type Subpool struct {
    Name    string
    Owner   string        // Agent LUName
    Created time.Time
    Keys    []string      // Registry keys owned by this agent
}

type SubpoolManager struct {
    mu       sync.RWMutex
    subpools map[string]*Subpool
}

func (sm *SubpoolManager) Create(owner string) *Subpool
func (sm *SubpoolManager) Release(owner string) []string  // returns freed keys
func (sm *SubpoolManager) Get(owner string) *Subpool
```

### 4. Checkpoint (`checkpoint.go`, ~50 lines)

**z/OS lineage**: JES2 Checkpoint. Shared job state so multiple Cadence
initiators can coordinate without stepping on each other.

```go
package shared

type JobState struct {
    ID          string
    Status      string   // queued | running | done | failed
    ClaimedBy   string   // Agent LUName (who picked it up)
    SubmittedAt time.Time
    CompletedAt time.Time
    Result      string
}

type CheckpointStore struct {
    mu   sync.RWMutex
    Jobs map[string]*JobState
}

func (cs *CheckpointStore) Claim(jobID, agent string) bool    // atomic claim
func (cs *CheckpointStore) Release(jobID string)
func (cs *CheckpointStore) Get(jobID string) *JobState
func (cs *CheckpointStore) ListByStatus(status string) []*JobState
```

### 5. PARMLIB (`parmlib.go`, ~120 lines)

**z/OS lineage**: SYS1.PARMLIB.

One directory, one YAML member per subsystem. No single monolithic config.

```go
package shared

type PARMLIB struct {
    path string  // etc/macs-parmlib/
}

func NewPARMLIB(path string) *PARMLIB

// Load reads a named member (e.g., "IEASYS", "REGULAT") and
// unmarshals it into the provided struct.
func (p *PARMLIB) Load(member string, dest interface{}) error

// List returns all member names in the PARMLIB directory.
func (p *PARMLIB) List() ([]string, error)
```

**Member naming** (8-char max, uppercase):

```
etc/macs-parmlib/
├── IEASYS.yaml       # system startup: kernel params, subsystem list
├── REGULAT.yaml      # §2 Regulator
├── SANCTUM.yaml      # §3 Sanctum
├── LOOM.yaml         # §3b Loom
├── CHRONICL.yaml     # §4 Chronicle
├── XVAL.yaml         # §5 XVal
├── CADENCE.yaml      # §6 Cadence
├── CURATOR.yaml      # §7 Curator
├── NEXUS.yaml        # §8 Nexus
├── GAUGE.yaml        # §9 Gauge
├── SEAL.yaml         # §10 Seal
├── RELAY.yaml        # §11 Relay
├── WARDEN.yaml       # §12 Warden
├── PULSE.yaml        # §13 Pulse
└── CONSOLxx.yaml     # §14 Console
```

---

## Implementation Order

| Step | Component | Tests | Priority |
|:--:|------|:--:|:--:|
| 1 | `parmlib.go` + PARMLIB dir | 4 | Foundation |
| 2 | `types.go` (AgentState, shared types) | — | Foundation |
| 3 | `registry.go` | 5 | Core |
| 4 | `dispatch.go` | 2 | Core |
| 5 | `subpool.go` | 3 | Standard |
| 6 | `checkpoint.go` | 3 | Standard |
| | **Total** | **17** | |

---

## After v0.2: POC Readiness

With Registry + Dispatch + PARMLIB, POC-5 can run:

```go
// POC-5: Token budget degradation
parmlib := shared.NewPARMLIB("etc/macs-parmlib")

// Load config per subsystem
var regulatCfg RegulatConfig
parmlib.Load("REGULAT", &regulatCfg)

var wardenCfg  WardenConfig
parmlib.Load("WARDEN", &wardenCfg)

// Shared state via Registry — no direct imports
reg := shared.NewRegistry()
reg.UpdateAgent("research.prod", func(as *AgentState) {
    as.TokenBudget.Level = "yellow"
})

// Warden reads the same state
agent := reg.GetAgent("research.prod")
if agent.TokenBudget.Level == "yellow" {
    // trigger degrade action
}
```
