# MACS §14 Console — Development Specification

> **Implementation target**: dev team
> **Reviewer / Acceptor**: 邝谧 (Hermes Agent)
> **Canonical spec**: [macs-governance-spec.md §14](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)

## Architecture Overview

```
                    ┌──────────────────┐
                    │   Console (§14)   │
                    │                  │
     Interactive ──►│  Feishu Cards    │──► Feishu API
     Headless    ──►│  CLI (REPL)      │──► stdout
     Embedded    ──►│  MCP Server      │──► MCP Client
                    │                  │
                    └──────┬───────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Pulse(§13)   Warden(§12)   Chronicle(§4)
         Gauge(§9)    Cadence(§6)   Seal(§10)
         Regulator(§2) Sanctum(§3)  Curator(§7)
```

Console is a **read/write aggregation layer** — it does NOT implement subsystem logic. Every command delegates to the relevant subsystem package.

## Repository

```
deeparchi-ai/macs-console-go
├── LICENSE               # MIT
├── README.md             # subsystem description
├── go.mod                # module github.com/deeparchi-ai/macs-console-go
├── pkg/console/
│   ├── cli.go            # CLI router + REPL loop
│   ├── commands.go       # command dispatch table
│   ├── mcp.go            # MCP server tool definitions
│   ├── types.go          # shared types: Command, Mode, etc.
│   ├── status.go         # "macs-console status" — Pulse + Gauge + Regulator
│   ├── agentctl.go       # "macs-console agent *" — Warden
│   ├── job.go            # "macs-console job *" — Cadence
│   ├── audit.go          # "macs-console audit query" — Chronicle
│   ├── metrics.go        # "macs-console metric show" — Gauge
│   ├── identity.go       # "macs-console identity *" — Seal
│   ├── policy.go         # "macs-console policy *" — Warden
│   ├── output.go         # formatters: text, json, feishu-card
│   └── console_test.go   # all tests
└── cmd/
    └── macs-console/
        └── main.go       # entry point
```

## v0.1 Scope: Headless Mode First

For v0.1, **only Headless (CLI) mode is required**. Interactive (Feishu) and Embedded (MCP) are v0.2+.

### Phase 1 — v0.1 (this sprint)
- [x] Headless CLI with all 8 command groups
- [x] `--output json` flag on every command
- [x] Subsystem integration stubs (standalone mode — no external deps in v0.1)

### Phase 2 — v0.2 (next sprint)
- [ ] Feishu interactive card renderer
- [ ] MCP server tool set

---

## Type Definitions

All types go in `pkg/console/types.go`.

```go
package console

// Mode is the Console operating mode.
type Mode int
const (
    ModeHeadless    Mode = iota  // CLI
    ModeInteractive              // Feishu cards
    ModeEmbedded                 // MCP tools
)

// Command represents a parsed CLI command.
type Command struct {
    Noun    string            // "status", "agent", "job", ...
    Verb    string            // "list", "start", "stop", "query", ...
    Args    []string          // positional args
    Flags   map[string]string // --key=value
    Mode    Mode
}

// OutputFormat controls how results are rendered.
type OutputFormat int
const (
    FormatText OutputFormat = iota  // human-readable table
    FormatJSON                      // machine-readable
)

// AgentSummary is the console-facing agent view.
type AgentSummary struct {
    LUName      string
    Status      string   // "online", "offline", "crashed"
    Subsystem   string   // owner subsystem
    LastSeen    string   // ISO8601
    CrashCount  int
}

// JobSummary is the console-facing job view.
type JobSummary struct {
    ID          string
    Status      string   // "queued", "running", "done", "failed"
    SubmittedAt string
    CompletedAt string
    Agent       string
    Result      string   // truncated output, first 200 chars
}

// AuditEntry is the console-facing audit record.
type AuditEntry struct {
    TraceID     string
    Agent       string
    Event       string
    Timestamp   string
    Details     string
}

// IdentitySummary is the console-facing identity view.
type IdentitySummary struct {
    LUName      string
    Status      string   // "active", "rotating", "revoked"
    PublicKeyHash string
    ExpiresAt   string
}

// PolicySummary is the console-facing policy view.
type PolicySummary struct {
    Name            string
    Condition       string
    Actions         []string
    EscalationLevel string
    Active          bool
}
```

## CLI Contract

### Entry Point

```go
// cmd/macs-console/main.go
func main() {
    // 1. Parse args: macs-console <noun> <verb> [--flags] [--output json|text]
    // 2. Dispatch to Command handler
    // 3. Format output (text table or JSON)
    // 4. Exit 0 on success, non-0 on error
}
```

### Command Router

```go
// pkg/console/commands.go
var commandTable = map[string]map[string]CommandHandler{
    "status": {
        "":        handleStatus,          // macs-console status
    },
    "agent": {
        "list":    handleAgentList,       // macs-console agent list
        "start":   handleAgentStart,      // macs-console agent start <lu-name>
        "stop":    handleAgentStop,       // macs-console agent stop <lu-name>
        "restart": handleAgentRestart,    // macs-console agent restart <lu-name>
    },
    "job": {
        "list":    handleJobList,         // macs-console job list [--status=<s>]
        "output":  handleJobOutput,       // macs-console job output <job-id>
    },
    "audit": {
        "query":   handleAuditQuery,      // macs-console audit query [--agent=<a>] [--since=<t>] [--trace=<id>]
    },
    "metric": {
        "show":    handleMetricShow,      // macs-console metric show [--subsystem=<s>] [--window=<d>]
    },
    "identity": {
        "list":    handleIdentityList,    // macs-console identity list [--status=<s>]
        "register": handleIdentityRegister, // macs-console identity register --lu=<n> --card=<u> --key=<h>
        "rotate":  handleIdentityRotate,  // macs-console identity rotate --lu=<n> --new-key=<h>
        "revoke":  handleIdentityRevoke,  // macs-console identity revoke --lu=<n> --reason=<t>
    },
    "policy": {
        "list":    handlePolicyList,      // macs-console policy list
        "edit":    handlePolicyEdit,      // macs-console policy edit --name=<n> --action=<a>
        "activate": handlePolicyActivate, // macs-console policy activate --name=<n>
    },
}
```

### Output Formatter

```go
// pkg/console/output.go

// RenderText formats output as a human-readable table.
// Uses aligned columns with headers.
func RenderText(headers []string, rows [][]string) string

// RenderJSON formats output as JSON.
func RenderJSON(v interface{}) string
```

---

## Command Handlers — Implementation Specification

### `macs-console status`

**Input**: none
**Output format**:

```
MAC System Status: HEALTHY
┌────────────────┬──────────┬──────────────────────────────┐
│ Subsystem      │ Status   │ Detail                       │
├────────────────┼──────────┼──────────────────────────────┤
│ Regulator      │ ONLINE   │ CPU: 12%, Tokens: 45%        │
│ Sanctum        │ ONLINE   │ Active: 8, Blocked: 0        │
│ Loom           │ ONLINE   │ Fork-points: 3 active        │
│ Chronicle      │ ONLINE   │ Records: 14,502              │
│ XVal           │ ONLINE   │ Tri-model, 2/3 rate: 87%     │
│ Cadence        │ ONLINE   │ Queue: 2 queued, 1 running   │
│ Curator        │ ONLINE   │ Hot: 45% used                │
│ Nexus          │ ONLINE   │ Connections: 12              │
│ Gauge          │ ONLINE   │ Alerts: 0 active             │
│ Seal           │ ONLINE   │ Identities: 8                │
│ Relay          │ ONLINE   │ Cluster: 5 members           │
│ Warden         │ ONLINE   │ Policies: 4 active           │
│ Pulse          │ ONLINE   │ All checks passing           │
│ Console        │ ONLINE   │ Mode: headless               │
└────────────────┴──────────┴──────────────────────────────┘
```

**v0.1 approach**: Each subsystem status is a stub that returns "ONLINE" with mock detail.

**`--output json`**:

```json
{
  "status": "healthy",
  "subsystems": [
    {"name": "Regulator", "status": "online", "detail": "CPU: 12%, Tokens: 45%"},
    ...
  ]
}
```

### `macs-console agent list`

**Input**: none
**Output**: table of AgentSummary rows
**v0.1**: Returns 3 hardcoded agents for demo

### `macs-console agent start/stop/restart <lu-name>`

**Input**: LU name (positional arg)
**Output**: confirmation message with Loom fork-point for start
**v0.1**: Mock — prints "Agent <lu-name> started/stopped/restarted. Fork-point: <timestamp>"

### `macs-console job list/output`

**Input**: optional `--status` flag (list) or job ID (output)
**Output**: table of JobSummary / job output text
**v0.1**: Mock job queue with 3-4 entries

### `macs-console audit query`

**Input**: optional `--agent`, `--since`, `--trace` flags
**Output**: table of AuditEntry rows
**v0.1**: Mock 5 audit entries

### `macs-console metric show`

**Input**: optional `--subsystem`, `--window` flags
**Output**: metric values with timestamp
**v0.1**: Mock Gauge data

### `macs-console identity list/register/rotate/revoke`

**Input**: depends on sub-command
**Output**: table / confirmation
**v0.1**: In-memory mock identity registry

### `macs-console policy list/edit/activate`

**Input**: depends on sub-command
**Output**: table / confirmation
**v0.1**: In-memory mock policy store

---

## Testing Requirements

- **Minimum 20 tests**, covering:
  - CLI argument parsing (valid + invalid flags)
  - All 8 command groups return non-empty output
  - `--output json` produces valid JSON on every command
  - Unknown commands produce error exit
  - Missing required args produce error exit
- Use `go test ./...` standard
- No external dependencies (pure Go stdlib)

## Go Setup

```bash
go mod init github.com/deeparchi-ai/macs-console-go
GOPROXY=https://goproxy.cn,direct
go version  # must be ≥ 1.21
```

## Integration Points (v0.2+)

In v0.2, mock stubs are replaced with real subsystem calls:

| Handler | v0.1 (mock) | v0.2 (real) |
|---------|:--:|------|
| status | hardcoded ONLINE | Pulse.Status() + Gauge.Aggregate() + Regulator stats |
| agent start | print confirmation | Warden recovery path → Loom fork-point |
| agent stop | print confirmation | Warden graceful shutdown |
| agent restart | print confirmation | Warden crash recovery full path |
| job list | hardcoded queue | Cadence job queue |
| job output | hardcoded text | Cadence job output → Chronicle trace |
| audit query | hardcoded entries | Chronicle query by trace/agent/time |
| metric show | hardcoded values | Gauge registry query |
| identity * | in-memory map | Seal registry |
| policy * | in-memory map | Warden policy engine |

## Deliverables (v0.1)

1. [ ] `go.mod` + `go.sum`
2. [ ] `LICENSE` (MIT)
3. [ ] `README.md` (subsystem description)
4. [ ] `cmd/macs-console/main.go`
5. [ ] `pkg/console/` — all files listed above
6. [ ] `go test ./...` — all 20+ tests pass
7. [ ] Git commit: `feat(console): v0.1 — headless CLI with 8 command groups covering all 13 subsystems`
8. [ ] Push to `deeparchi-ai/macs-console-go` main

## Acceptance Gate

The Hermes Agent will run acceptance verification against the criteria in
[console-acceptance-tests.md](console-acceptance-tests.md). All 15 checks
must pass before merging to main.
