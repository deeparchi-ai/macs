# MACS Kernel v0.2 — Development Spec

> **Target repo**: `deeparchi-ai/macs-kernel-go`
> **Design doc**: [kernel-v0.2-design.md](kernel-v0.2-design.md)
> **Acceptor**: 邝谧 (Hermes Agent)

## Scope

Add Integration Layer to existing `macs-kernel-go` v0.1. New code goes in `pkg/kernel/shared/`.

## File Structure

```
macs-kernel-go/
├── pkg/kernel/
│   ├── arbiter.go / brake.go / audit.go / trace.go / lock.go / types.go  (v0.1 ✅)
│   │
│   └── shared/                    ← v0.2 NEW
│       ├── types.go               ← AgentState, TokenBudget, HealthStatus, JobState
│       ├── parmlib.go             ← PARMLIB loader
│       ├── registry.go            ← CSA: shared agent state
│       ├── dispatch.go            ← SVC Table: function dispatch
│       ├── subpool.go             ← GETMAIN: agent resource groups
│       ├── checkpoint.go          ← JES2 Checkpoint: job state
│       ├── shared_test.go         ← 17+ tests
│       └── shared_integration_test.go ← cross-component tests (optional bonus)
│
└── etc/macs-parmlib/              ← PARMLIB member directory
    ├── IEASYS.yaml
    ├── REGULAT.yaml / SANCTUM.yaml / LOOM.yaml / CHRONICL.yaml / XVAL.yaml
    ├── CADENCE.yaml / CURATOR.yaml / NEXUS.yaml / GAUGE.yaml
    ├── SEAL.yaml / RELAY.yaml / WARDEN.yaml / PULSE.yaml / CONSOLxx.yaml
```

## Component Specs

### 1. `shared/types.go` (~60 lines)

Define shared types that all subsystems access via Registry:

```go
package shared

type TokenBudget struct {
    Level string  // "green" | "yellow" | "red" | "black"
    Limit int
    Used  int
}

type HealthStatus int
const (
    StatusHealthy   HealthStatus = iota
    StatusDegraded
    StatusImpaired
    StatusDown
)

type AgentState struct {
    LUName       string
    TokenBudget  TokenBudget
    TrustScore   float64
    Health       HealthStatus
    Heartbeat    time.Time
    CrashCount   int
    ForkPoint    string
    ContextHot   bool
    Identities   []IdentityRef
}

type IdentityRef struct {
    LUName        string
    Status        string   // active | rotating | revoked
    PublicKeyHash string
}

type BrakeRef struct {
    Name  string
    State string   // closed | open | half-open
}

type JobState struct {
    ID          string
    Status      string
    ClaimedBy   string
    SubmittedAt time.Time
    CompletedAt time.Time
    Result      string
}
```

### 2. `shared/parmlib.go` (~120 lines)

```go
package shared

type PARMLIB struct {
    path string
}

func NewPARMLIB(path string) *PARMLIB

// Load reads a YAML member file and unmarshals into dest.
// Member name is case-insensitive uppercase (8-char convention).
// Example: parmlib.Load("REGULAT", &cfg)
func (p *PARMLIB) Load(member string, dest interface{}) error

// List returns all .yaml member names in the PARMLIB directory.
func (p *PARMLIB) List() ([]string, error)

// Path returns the PARMLIB directory path.
func (p *PARMLIB) Path() string
```

Behavior:
- Looks for `<member>.yaml` or `<MEMBER>.yaml` in the PARMLIB directory
- Returns error if member not found
- Returns error if YAML unmarshal fails
- `List()` returns member names WITHOUT .yaml suffix

### 3. `shared/registry.go` (~100 lines)

```go
package shared

type Registry struct {
    mu     sync.RWMutex
    Agents map[string]*AgentState
    CBs    map[string]*BrakeRef
    Jobs   map[string]*JobState
}

func NewRegistry() *Registry

// GetAgent returns a snapshot copy of the agent state.
// Returns nil if agent not found.
func (r *Registry) GetAgent(luName string) *AgentState

// UpdateAgent atomically reads and modifies agent state.
// Creates the agent entry if it doesn't exist.
func (r *Registry) UpdateAgent(luName string, fn func(*AgentState))

// ListAgents returns all agents matching the filter.
// If filter is nil, returns all agents.
func (r *Registry) ListAgents(filter func(*AgentState) bool) []*AgentState

func (r *Registry) AgentCount() int

// ── Circuit Breaker operations ──
func (r *Registry) RegisterCB(name string, state string)
func (r *Registry) UpdateCB(name string, state string)
func (r *Registry) GetCB(name string) *BrakeRef

// ── Job operations ──
func (r *Registry) RegisterJob(job *JobState)
func (r *Registry) GetJob(jobID string) *JobState
func (r *Registry) ListJobs(status string) []*JobState
```

### 4. `shared/dispatch.go` (~50 lines)

```go
package shared

type AdmitFunc func(AdmissionRequest) AdmissionResult

type DispatchTable struct {
    Admit  AdmitFunc
    Status func() string
}

func NewDispatchTable() *DispatchTable
```

`AdmissionRequest` and `AdmissionResult` are defined in `kernel` package (v0.1 types.go). The `shared` package imports `kernel`.

### 5. `shared/subpool.go` (~60 lines)

```go
package shared

type Subpool struct {
    Name    string
    Owner   string
    Created time.Time
    Keys    []string
}

type SubpoolManager struct {
    mu       sync.RWMutex
    subpools map[string]*Subpool  // owner → subpool
}

func NewSubpoolManager() *SubpoolManager

// Create creates a subpool for an agent. Idempotent.
func (sm *SubpoolManager) Create(owner string) *Subpool

// Release frees all resources owned by the agent. Returns freed keys.
func (sm *SubpoolManager) Release(owner string) []string

// Get returns the subpool for an agent, or nil.
func (sm *SubpoolManager) Get(owner string) *Subpool

// AddKey appends a key to an agent's subpool.
func (sm *SubpoolManager) AddKey(owner, key string)

// Count returns total number of active subpools.
func (sm *SubpoolManager) Count() int
```

### 6. `shared/checkpoint.go` (~60 lines)

```go
package shared

type CheckpointStore struct {
    mu   sync.RWMutex
    jobs map[string]*JobState
}

func NewCheckpointStore() *CheckpointStore

// Claim attempts to atomically claim a job. Returns true if successful.
// A job can only be claimed once (status empty → claimed).
func (cs *CheckpointStore) Claim(jobID, agent string) bool

// Release marks a claimed job back to unclaimed.
func (cs *CheckpointStore) Release(jobID string)

// Get returns a job by ID.
func (cs *CheckpointStore) Get(jobID string) *JobState

// List returns all jobs matching the status filter. "" = all.
func (cs *CheckpointStore) List(status string) []*JobState

// Register adds a new job to the store.
func (cs *CheckpointStore) Register(job *JobState)
```

---

## PARMLIB Member Templates

Each member file must be a valid YAML with at minimum an empty struct:

```yaml
# etc/macs-parmlib/IEASYS.yaml
kernel:
  max_agents: 256
  dispatch_mode: strict

subsystems:
  - regulat
  - sanctum
  - loom
  - chronicl
  - xval
  - cadence
  - curator
  - nexus
  - gauge
  - seal
  - relay
  - warden
  - pulse
  - console
```

```yaml
# etc/macs-parmlib/REGULAT.yaml
importance_classes:
  critical: 0
  high: 1
  standard: 2

token_budget:
  daily_limit: 1000000
  yellow_threshold: 0.7
  red_threshold: 0.9
```

Other member files can be empty stubs for v0.2:

```yaml
# etc/macs-parmlib/SANCTUM.yaml
# §3 Sanctum — placeholder for v0.3
```

---

## Testing (17+ tests)

### parmlib_test.go (4 tests)
1. `TestPARMLIB_Load_IEASYS` — loads IEASYS.yaml, verifies kernel params
2. `TestPARMLIB_Load_NotFound` — returns error for missing member
3. `TestPARMLIB_Load_BadYAML` — returns error for invalid YAML
4. `TestPARMLIB_List` — returns all member names

### registry_test.go (5 tests)
5. `TestRegistry_GetAgent_NotFound` — returns nil
6. `TestRegistry_UpdateAgent_Creates` — first update creates entry
7. `TestRegistry_UpdateAgent_Modifies` — atomic RMW across goroutines
8. `TestRegistry_ListAgents_Filter` — filter by TokenBudget level
9. `TestRegistry_Concurrent` — 100 goroutines updating different agents, no panic

### dispatch_test.go (1 test)
10. `TestDispatchTable_Admit` — registered function is callable

### subpool_test.go (3 tests)
11. `TestSubpool_Create` — creates subpool for agent
12. `TestSubpool_Release_FreesKeys` — Release returns all keys
13. `TestSubpool_Release_RemovesPool` — pool gone after release

### checkpoint_test.go (4 tests)
14. `TestCheckpoint_Claim_Atomic` — two goroutines claim same job, only one wins
15. `TestCheckpoint_Release` — release resets claim
16. `TestCheckpoint_Register_Get` — register then get
17. `TestCheckpoint_List_Filter` — list by status

---

## Go Setup

```go
// pkg/kernel/shared imports:
import "github.com/deeparchi-ai/macs-kernel-go/pkg/kernel"  // for types: AdmissionRequest, etc.

// go.mod already exists: module github.com/deeparchi-ai/macs-kernel-go
```

External deps: `gopkg.in/yaml.v3` for PARMLIB YAML parsing.

```bash
cd ~/macs-kernel-go
go get gopkg.in/yaml.v3
```

## Deliverables

1. [ ] `pkg/kernel/shared/` — 6 Go files (types/parmlib/registry/dispatch/subpool/checkpoint)
2. [ ] `pkg/kernel/shared/shared_test.go` — 17+ tests
3. [ ] `etc/macs-parmlib/` — all 15 member yamls
4. [ ] `go test ./...` — v0.1 31 tests + v0.2 17 tests = 48 total, all PASS
5. [ ] Commit: `feat(kernel): v0.2 integration layer — PARMLIB+Registry+Dispatch+Subpool+Checkpoint`
6. [ ] Push to main
