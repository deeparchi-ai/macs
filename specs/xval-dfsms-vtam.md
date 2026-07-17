# MACS §5 / §7 / §8 — XVal, DFSMS, VTAM

## Specialized Subsystems for Multi-Agent Governance

> **DeepArchi · 邝谧**  
> 2026-07-18 · Working Draft v0.1  
> Status: Design · Pre-implementation

---

## §5 — XVal: Cross-Validation for Subjective Agents

### 5.1 Problem

Subjective agents (architecture, strategy, product, risk) produce opinions, not facts. A single model's output is not verifiable by computation — there is no "correct answer" to "which architecture pattern fits this use case."

The DeepArchi design principle: **subjective agents require dual-model cross-validation.** Objective agents (engineering, data, market) can run single-model.

### 5.2 Protocol

```
Primary Model → produces decision D
                   │
                   ▼
Audit Model   → evaluates D: agree / disagree / refine
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
     AGREE      DISAGREE    REFINE
        │          │          │
        ▼          ▼          ▼
    Accept D    Escalate    Merge D + audit notes
                to human
```

### 5.3 Three-Tier Escalation

| Tier | Condition | Resolution |
|:----:|-----------|------------|
| **L1** | Both models agree | Auto-accept |
| **L2** | Disagree on implementation detail | Audit model's refinement applied |
| **L3** | Disagree on core decision | Escalate to human |

### 5.4 Configuration

```go
type XValConfig struct {
    PrimaryModel  string   // e.g., "claude-sonnet-4"
    AuditModel    string   // e.g., "deepseek-v4" — MUST be different family
    AutoAcceptL1  bool     // true for production
    EscalationFn  string   // callback for human-in-the-loop
    AuditLogPath  string   // where to write cross-validation records
}
```

### 5.5 Key Constraint

**Primary and audit models MUST be from different providers.** Cross-validating Claude against Claude-Sonnet from the same lab is not validation — it's an echo. At minimum: different model families; ideally: different providers.

### 5.6 Implementation (v0.1 target: ~200 lines Go)

---

## §7 — DFSMS: Knowledge Lifecycle & Memory Compression

### 7.1 Problem

Agent sessions accumulate context: conversation history, tool results, subagent outputs, retrieved documents. Context windows are finite (128K–1M tokens). Without lifecycle management, old context is either:
- **Dropped blindly** (FIFO eviction → lost critical info)
- **Kept entirely** (cost explosion + attention dilution)

z/OS DFSMS (Data Facility Storage Management Subsystem) solved this for disk storage in 1988: tiered storage (high-speed → nearline → archive → tape), automatic migration based on access patterns, and compression.

### 7.2 Tiered Context Model

```
┌─────────────────────────────────────────────┐
│  Tier 0: Hot Context (last 10 turns)         │
│  Full fidelity, uncompressed                 │
│  Size: ~50K tokens                           │
├─────────────────────────────────────────────┤
│  Tier 1: Warm Context (last 10–50 turns)     │
│  Summarized, key decisions preserved         │
│  Size: ~10K tokens                           │
├─────────────────────────────────────────────┤
│  Tier 2: Cold Context (session history)      │
│  Bullet-point summary only                   │
│  Size: ~1K tokens                            │
├─────────────────────────────────────────────┤
│  Tier 3: Archive (across sessions)           │
│  Searchable index only, retrieve on demand   │
│  Size: unlimited (stored externally)         │
└─────────────────────────────────────────────┘
```

### 7.3 Migration Triggers

```go
type MigrationPolicy struct {
    HotToWarm     TokenThreshold   // e.g., 50K tokens → compress oldest to warm
    WarmToCold    TokenThreshold   // e.g., 100K tokens → compress oldest to cold
    ColdToArchive SessionBoundary  // on session end: compress cold to archive
}
```

### 7.4 Compression Strategies

| Tier Transition | Strategy | Lossiness |
|:---|---:|:---:|
| Hot → Warm | LLM summarization with key-decision extraction | Acceptable |
| Warm → Cold | Bullet-point extraction (template-based) | High |
| Cold → Archive | Embedding-based indexing + keyword extraction | Total |

### 7.5 Recall

When an agent needs historical context, it queries the archive:

```go
func (dfsms *DFSMS) Recall(query string, sessionID string) ([]ContextChunk, error)
```

The archive returns ranked chunks. The agent decides whether to promote them to warm tier.

### 7.6 Implementation (v0.1 target: ~250 lines Go)

---

## §8 — VTAM: Protocol Admission & Multi-Transport

### 8.1 Problem

Multi-agent systems communicate over heterogeneous transports: HTTP, gRPC, WebSocket, stdio, message queues. Each transport has different semantics (streaming vs. request-response, persistent vs. ephemeral). Agents should not care about transport details — they should care about the agent they're talking to.

z/OS VTAM (Virtual Telecommunications Access Method) solved this in 1974: applications talked to VTAM using LU names; VTAM handled the physical network (SNA, TCP/IP, X.25) transparently.

### 8.2 Agent LU Names

Every MACS agent has a Logical Unit (LU) name — a stable identifier independent of transport:

```
Agent LU name: "research-agent.prod.deeparchi.ai"
Resolves to:
  - A2A (HTTP):  https://research-agent.prod.deeparchi.ai/a2a
  - A2A (gRPC):  grpc://research-agent.prod.deeparchi.ai:50051
  - MCP (stdio):  mcp://research-agent.prod.deeparchi.ai (via gateway)
```

### 8.3 Admission Control

Before an agent can communicate with another, VTAM checks:

```go
type AdmissionRule struct {
    SourceAgent  string            // who wants to connect
    TargetAgent  string            // who they want to reach
    AllowedMethods []string        // tasks/send, tasks/get, etc.
    MaxRate      int               // requests per minute
    RequireAuth  bool              // mutual TLS / API key
    TimeWindow   *TimeCondition    // when connections are allowed
}
```

### 8.4 Transport Negotiation

When Agent A wants to talk to Agent B:

```
1. Agent A: "I need to reach `research-agent` with priority HIGH"
2. VTAM:    Look up LU name → discover available transports
3. VTAM:    Select best transport: gRPC (lowest latency) > HTTP > WebSocket
4. VTAM:    Check admission rules → allowed
5. VTAM:    Establish connection, inject trace context (§4)
6. Agent A: Receive connection handle, proceed with A2A call
```

### 8.5 Circuit-Level Observability

VTAM records:
- Connection attempts (allowed / denied)
- Transport selection rationale
- Latency per transport
- Circuit failures and failover

All fed into SMF-equivalent audit trail (§4).

### 8.6 Implementation (v0.1 target: ~200 lines Go)

---

## Cross-Cutting Properties

| Property | XVal | DFSMS | VTAM |
|----------|:----:|:-----:|:----:|
| Fail-open? | No (escalate to human) | Yes (drop cold ctx, keep working) | No (deny unknown) |
| Audit trail? | Every cross-val result | Migration events | Every connection |
| License risk? | None (stdlib) | None (stdlib) | None (stdlib) |
| MVP lines | ~200 | ~250 | ~200 |

---

## Relationship to Existing MACS Systems

```
                    ┌─────────────────┐
                    │   VTAM (§8)     │
                    │  Protocol       │
                    │  Admission      │
                    └────────┬────────┘
                             │ routes connections
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│  Agent A        │ │  Agent B     │ │  Agent C        │
│  (orchestrator) │ │  (subagent)  │ │  (subagent)     │
└────────┬────────┘ └──────┬───────┘ └────────┬────────┘
         │                 │                   │
         └─────────────────┼───────────────────┘
                           │ decisions
                           ▼
                  ┌─────────────────┐
                  │   XVal (§5)     │
                  │   Cross-Validate│
                  │   (if subjective)│
                  └────────┬────────┘
                           │ verified decisions
                           ▼
                  ┌─────────────────┐
                  │  DFSMS (§7)     │
                  │  Context        │
                  │  Lifecycle      │
                  └─────────────────┘
```

---

*DeepArchi · 深度架构*
