# MACS §1 — Agent Authorization Model

## RACF Dataset/Field-Level Security for Multi-Agent Tool Access

> **DeepArchi · 邝谧**  
> 2026-07-18 · Working Draft v0.1  
> Status: Design · Pre-implementation

---

## Abstract

Existing agent frameworks treat tool access as binary: an agent either has a tool or it doesn't. This is the equivalent of giving every CICS transaction access to every dataset — which no production mainframe has done since 1976.

RACF (Resource Access Control Facility) introduced four concepts that map directly to agent security:

1. **Resource profiles with access levels** — not just "can call," but at what permission level
2. **Program pathing** — a transaction's authority depends on which program called it through which path
3. **Conditional access** — time-of-day, terminal-id, security-label predicates
4. **Universal auditing** — every access decision produces an SMF record

This specification ports those four concepts to the agent domain.

---

## 1. Agent Identity Model

### 1.1 Principal

Every agent invocation has a principal — the ultimate accountable entity. In MACS, this is the human user or service account that initiated the workflow.

```
┌─────────────────────────────────────────┐
│  Principal                               │
│  ├── principal_id: "kuangmi"             │
│  ├── groups: ["architects", "admin"]     │
│  ├── security_label: "internal"          │
│  └── attributes: {                       │
│        dept: "architecture",             │
│        clearance: "restricted"           │
│      }                                   │
└─────────────────────────────────────────┘
```

### 1.2 Agent Identity

Each agent has its own identity, distinct from its principal. An agent's authority is the **intersection** of its own profile and its principal's.

```
Agent Identity = Agent_Profile ∩ Principal_Profile
```

This is the SURROGAT class pattern: Agent B acts on behalf of Principal P, but only within the bounds of Agent B's own authority.

### 1.3 Delegation Chain

When Agent A delegates to Agent B, B's authority is further bounded:

```
Effective Authority = Agent_B_Profile ∩ Agent_A_Profile ∩ Principal_Profile
```

Each hop in the chain NARROWS authority — never expands it.

---

## 2. Tool Resource Profiles

### 2.1 Profile Structure

Every tool in MACS has a resource profile:

```go
type ToolProfile struct {
    ToolName    string              // e.g., "filesystem.write"
    AccessLevel AccessLevel         // granular permission
    ParamScopes []ParamScope        // field-level constraints
    Pathing     *PathingRule        // call-chain requirements
    Conditions  []Condition         // runtime predicates
    AuditLevel  AuditLevel          // SMF-equivalent detail
}

type AccessLevel int
const (
    AccessNone    AccessLevel = iota  // 0: cannot call
    AccessExecute                     // 1: call, no data inspection
    AccessRead                        // 2: call + see results
    AccessUpdate                      // 3: call + modify
    AccessAdmin                       // 4: modify tool profile itself
)
```

### 2.2 Parameter-Level Access (Field-Level Security)

RACF's field-level security maps to parameter-level constraints:

```go
type ParamScope struct {
    ParamName   string              // which parameter
    AllowValues []string            // allowed values (enum)
    DenyPattern string              // regex deny-list
    MaxLength   int                 // size limit
    MaxTokens   int                 // budget limit per call
}
```

Example: Agent can call `web_search` but only with `site:arxiv.org` and a max query length of 200 chars.

### 2.3 Generic Profiles (Wildcards)

Like RACF generic profiles (`HLQ.**`), MACS supports prefix-based profiles:

```
Resource profile: "filesystem.*"  → matches filesystem.read, filesystem.write, filesystem.delete
Resource profile: "web_*"         → matches web_search, web_extract, web_scrape
```

More specific profiles override generic ones.

---

## 3. Program Pathing (Call-Chain Authorization)

### 3.1 The Problem

RACF's program pathing answers: "Is this CICS transaction allowed to access this dataset *given that it was called through this specific program path*?"

Agent equivalent: "Is Agent B allowed to call tool X *given that it was invoked by Agent A on behalf of Principal P*?"

### 3.2 Pathing Rule

```go
type PathingRule struct {
    RequiredCallers   []string   // at least one must be in the chain
    ForbiddenCallers  []string   // none may be in the chain
    MinChainDepth     int        // how many hops required
    MaxChainDepth     int        // delegation depth limit
}
```

Example: `filesystem.delete` requires the caller chain to include `orchestrator` agent — a CLI agent cannot delete files directly.

### 3.3 Transitive Trust Attenuation

Each delegation step reduces authority. After N hops, authority converges to zero unless explicitly re-authorized. Default: max 3 hops.

---

## 4. Conditional Access

### 4.1 Time-Based

```go
type TimeCondition struct {
    After     string   // "09:00"
    Before    string   // "18:00"
    DaysOfWeek []int   // 1=Monday
}
```

### 4.2 Budget-Based

```go
type BudgetCondition struct {
    MaxTokensPerHour  int
    MaxTokensPerDay   int
    MaxCostPerCall    float64   // $ limit
    MaxCostPerDay     float64
}
```

### 4.3 Context-Based

```go
type ContextCondition struct {
    RequireTaskType    string   // e.g., "research" only
    RequireContextID   string   // specific workflow
    ForbidContextIDs   []string // blacklisted workflows
}
```

### 4.4 Security Label (MLS)

```go
type LabelCondition struct {
    RequireClearance  string   // "internal", "restricted", "confidential"
    MaxDataLabel      string   // highest sensitivity agent can access
}
```

---

## 5. Enforcement Architecture

### 5.1 Decision Point (PEP)

Every tool call passes through a Policy Enforcement Point (PEP) — the MACS security gateway:

```
Agent → PEP → Tool
         │
         ├── 1. Resolve principal + agent identity
         ├── 2. Load tool profile
         ├── 3. Evaluate param scopes
         ├── 4. Check pathing rules
         ├── 5. Evaluate conditions
         ├── 6. Log decision to audit trail (§4)
         └── 7. Allow / Deny / Defer
```

### 5.2 Decision Outcomes

| Outcome | Meaning | Agent sees |
|---------|---------|------------|
| `allowed` | All checks passed | Normal result |
| `denied` | Hard block | "Tool not available" (no disclosure) |
| `deferred` | Needs human approval | "Awaiting authorization" |
| `scoped` | Allowed with parameter modification | Modified params (transparent) |

### 5.3 Scoped Access

When a param scope restricts a parameter, the PEP rewrites the call:

```
Agent calls: web_search(query="all secret projects site:internal.com")
PEP scopes:  web_search(query="site:arxiv.org", max_results=5)
```

The agent receives the scoped result — it doesn't need to know its request was modified. This preserves the RACF principle: deny without disclosure.

### 5.4 Fail-Open vs Fail-Closed

MACS security defaults to **fail-closed**: if the PEP cannot evaluate a rule, the call is denied. This is the opposite of MACS observability (which is fail-open). Security is the one MACS subsystem where breakage is preferable to bypass.

---

## 6. Audit Integration (§4)

Every security decision produces an audit record:

```json
{
  "audit_record": {
    "event_id": "sec-20260718-001",
    "principal_id": "kuangmi",
    "agent_id": "research-agent-01",
    "tool_name": "filesystem.write",
    "access_level": "update",
    "decision": "denied",
    "reason": "pathing rule: requires orchestrator in call chain",
    "param_modifications": null,
    "timestamp": "2026-07-18T10:00:00Z"
  }
}
```

This feeds into the SEP #3004 tamper-evident audit chain (§4 dimension).

---

## 7. License

Dependencies for the Go reference implementation:

| Dependency | License | Copyleft | Commercial OK |
|------------|---------|:--------:|:-------------:|
| stdlib only | Go BSD | No | ✅ |

Zero external dependencies by design — the security layer must have the smallest possible attack surface.

---

## 8. Implementation Plan

| Phase | Deliverable | Lines |
|:-----:|------------|:-----:|
| v0.1 | `ToolProfile` + `AccessLevel` + `ParamScope` data types | ~100 |
| v0.2 | PEP engine: evaluate identity + profile + param scopes | ~200 |
| v0.3 | Pathing rules + delegation chain resolution | ~150 |
| v0.4 | Conditions: time, budget, context, label | ~100 |
| v0.5 | Audit record emission (§4 integration) | ~50 |
| v0.6 | Hermes adapter: plug into Hermes tool dispatch | ~100 |

Total: ~700 lines Go. v0.1–v0.2 is the minimum viable surface.

---

*DeepArchi · 深度架构*
