# Cross-Protocol Trace Context Bridge

## A2A ↔ MCP Trace Context Propagation Specification v0.1

> **DeepArchi · 邝谧**  
> 2026-07-03 · Working Draft

---

## Abstract

The A2A (Agent-to-Agent) and MCP (Model Context Protocol) protocols each define W3C Trace Context propagation within their own protocol boundaries. When an A2A agent invokes an MCP tool — or an MCP server delegates to an A2A agent — the trace context must cross protocol boundaries. Without a canonical bridge, causal chains break, observability fragments, and distributed debugging becomes impossible.

This specification defines a **zero-configuration, bidirectional trace context bridge** that maps W3C Trace Context between A2A's `metadata` extension field and MCP's `params._meta` reserved keys. It extends neither protocol; it occupies their native extension points.

---

## 1. Motivation

### 1.1 The Causal Chain Problem

```
┌──────────────┐    A2A    ┌──────────────┐    MCP    ┌──────────────┐
│  Orchestrator│──────────→│ Research     │──────────→│ Web Search   │
│  Agent       │           │ Agent        │   MCP     │ Tool         │
│  trace=t1    │   t1→t1   │  trace=t1    │   ???     │  trace=t2    │
└──────────────┘           └──────────────┘           └──────────────┘
                                                                 │
                                    Without bridge: trace chain breaks ─┘
                                    Web Search tool's trace=t2 is orphaned
```

In a multi-agent system, an orchestrator sends an A2A task to a research agent, which calls an MCP web search tool. Both protocols support W3C Trace Context internally, but the trace stops at the protocol boundary. The MCP tool call gets a new, unconnected trace ID.

### 1.2 Why Not Just Use HTTP Headers?

HTTP headers (`traceparent`, `tracestate`) work for HTTP-based transports, but:
- MCP is often **stdio-based** (no HTTP headers)
- A2A supports gRPC and WebSocket (different header semantics)
- Message-level embedding survives queueing, batching, and retry

A message-level bridge works for ALL transports.

### 1.3 The SMF Analogy

IBM's SMF (System Management Facility) solved a similar problem in 1971: how to trace a transaction across CICS regions, DB2 calls, and MQ puts without a common protocol. The answer: **SMF type 110 records** with a shared **URID (Unit of Recovery ID)** that propagated through every boundary.

This specification applies the same principle: W3C `trace-id` is the URID.

---

## 2. Canonical Trace Context

The bridge uses W3C Trace Context Level 1 (`version: 00`), forward-compatible with Level 2.

### 2.1 Required Fields

| Field | W3C Key | Format | Required |
|-------|---------|--------|:--------:|
| Trace ID | `traceparent` | `00-{32-char-hex}-{16-char-hex}-{2-char-flags}` | ✅ |
| Trace State | `tracestate` | Comma-separated `vendor=value` pairs | ❌ |
| Baggage | `baggage` | Comma-separated `key=value` pairs | ❌ |

### 2.2 Bridge-Specific tracestate Entry

To identify bridge-originated traces, an additional `tracestate` entry:

```
deeparchi=br:{version}
```

Where `{version}` is the bridge spec version (e.g., `br:1`). This allows downstream systems to detect bridge-propagated traces and apply bridge-specific policies.

---

## 3. A2A Binding

### 3.1 Extension URI

```
https://deeparchi.ai/extensions/trace-context/v1
```

### 3.2 Agent Card Declaration

```json
{
  "capabilities": {
    "extensions": [
      {
        "uri": "https://deeparchi.ai/extensions/trace-context/v1",
        "description": "W3C Trace Context propagation for cross-protocol audit chains",
        "required": false
      }
    ]
  }
}
```

### 3.3 Message Metadata Embedding

Trace context is embedded in a message's `metadata` field under the extension URI key:

```json
{
  "message": {
    "role": "ROLE_USER",
    "parts": [{"text": "Search for recent papers on agent architectures"}],
    "metadata": {
      "https://deeparchi.ai/extensions/trace-context/v1": {
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        "tracestate": "deeparchi=br:1,congo=t61rcWkgMzE",
        "baggage": "agent_id=orchestrator-01"
      }
    }
  }
}
```

### 3.4 Artifact Metadata Embedding

Same structure for artifacts (tool results, generated content):

```json
{
  "artifactId": "search-results-001",
  "parts": [{"text": "10 papers found..."}],
  "metadata": {
    "https://deeparchi.ai/extensions/trace-context/v1": {
      "traceparent": "00-0af7651916cd43dd8448eb211c80319c-7b8acd6b9203331e-01",
      "tracestate": "deeparchi=br:1"
    }
  }
}
```

### 3.5 Span Semantics

| A2A Operation | OTel Span Name | Span Kind |
|---------------|----------------|-----------|
| `tasks/send` | `a2a.tasks/send {agent_name}` | CLIENT |
| `tasks/get` | `a2a.tasks/get {task_id}` | CLIENT |
| `message/send` | `a2a.message/send {agent_name}` | CLIENT |
| Message processing | `a2a.message/process` | SERVER |

---

## 4. MCP Binding

### 4.1 _meta Embedding

MCP reserves `traceparent`, `tracestate`, and `baggage` as unprefixed keys in `params._meta` (draft spec exception to prefix requirement).

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "web_search",
    "arguments": {"query": "agent architectures"},
    "_meta": {
      "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
      "tracestate": "deeparchi=br:1,congo=t61rcWkgMzE",
      "baggage": "agent_id=orchestrator-01"
    }
  }
}
```

### 4.2 Span Semantics

Per OpenTelemetry Semantic Conventions for MCP (PR #2083):

| MCP Method | OTel Span Name | Span Kind |
|------------|----------------|-----------|
| `tools/call` | `tools/call {tool_name}` | CLIENT |
| `tools/list` | `tools/list` | CLIENT |
| `resources/read` | `resources/read {uri}` | CLIENT |

### 4.3 Notification Handling

MCP notifications (messages without `id`) MUST propagate trace context but MUST NOT create new spans. Observations are attached to the parent span.

---

## 5. Bridge Behavior

### 5.1 A2A → MCP (Inbound Bridge)

When an A2A agent receives a message containing the trace context extension and subsequently calls an MCP tool:

```
INPUT:   A2A message with metadata[extension-uri].traceparent
OUTPUT:  MCP tools/call with params._meta.traceparent
```

**Algorithm:**

```
1. EXTRACT traceparent, tracestate, baggage from A2A message.metadata
2. GENERATE new span-id for the MCP call (16 hex chars, CSPRNG)
3. SET traceparent.flags: inherit sampled flag from A2A
4. PRESERVE tracestate: append "deeparchi=br:1" if not present
5. INJECT into MCP params._meta
6. CREATE OTel span: CLIENT, name="tools/call {tool_name}", parent=old_span_id
```

**Span Chain:**

```
A2A Orchestrator Agent (SERVER, trace=t, span=s1)
  └── A2A message/send (CLIENT, trace=t, span=s2, parent=s1)
      └── MCP tools/call web_search (CLIENT, trace=t, span=s3, parent=s2)
          └── Web Search Tool (SERVER, trace=t, span=s4, parent=s3)
```

### 5.2 MCP → A2A (Outbound Bridge)

When an MCP server (or tool) delegates work back to an A2A agent:

```
INPUT:   MCP tools/call with params._meta.traceparent
OUTPUT:  A2A message with metadata[extension-uri].traceparent
```

**Algorithm:**

```
1. EXTRACT traceparent, tracestate, baggage from MCP params._meta
2. GENERATE new span-id for the A2A message (16 hex chars, CSPRNG)
3. PRESERVE tracestate
4. INJECT into A2A message.metadata under extension URI
5. SET A2A-Extensions header (if HTTP transport)
6. CREATE OTel span: CLIENT, name="a2a.message/send {agent_name}", parent=old_span_id
```

### 5.3 Bridge Chaining (Multi-Hop)

The bridge is idempotent across multiple hops:

```
A2A → MCP → A2A → MCP → Tool
```

Each boundary generates a new span-id; the trace-id is invariant. The `deeparchi=br:1` tracestate entry signals "already bridged" — subsequent bridges MUST NOT re-wrap.

### 5.4 Error Handling

| Error | Behavior |
|-------|----------|
| No trace context in input | Start NEW trace (root span). Log warning. |
| Malformed traceparent | Log error. Start NEW trace. Do NOT propagate garbage. |
| Bridge not supported by target | Degrade gracefully: skip injection. Trace breaks at boundary. |
| Sampling decision = 0 | Propagate context (keep causal chain) but skip span creation. |

---

## 6. Audit Trail Semantics

### 6.1 Immutable Trace Chain

Each boundary crossing is recorded as:
- A **span event** with `event.name = "protocol.bridge"`
- Attributes: `bridge.from_protocol`, `bridge.to_protocol`, `bridge.spec_version`

### 6.2 Admission-Control Checkpoints

Extends the MCP Audit Record SEP (#3004) to include trace context:

```json
{
  "audit_records": [
    {
      "trace_id": "0af7651916cd43dd8448eb211c80319c",
      "span_id": "b7ad6b7169203331",
      "checkpoint": "admission_control",
      "decision": "allowed",
      "server_id": "mcp-gateway-01",
      "tool_name": "web_search",
      "client_info": {"name": "research-agent", "version": "1.0.0"}
    }
  ]
}
```

This creates a **complete audit chain** — from orchestrator decision → A2A delegation → MCP tool call → admission check → result — all linked by a single trace-id.

### 6.3 SMF Mapping

| SMF Record | Bridge Equivalent |
|-----------|-------------------|
| SMF 110 (CICS Transaction) | Trace root (orchestrator task) |
| URID (Unit of Recovery ID) | W3C trace-id |
| CICS Task Number | Span-id (parent-id chain) |
| CICS PCT Entry | Admission-control checkpoint |
| RACF Access Decision | Span event with auth attributes |
| SMF 101 (Accounting) | Span metrics (duration, token count) |

---

## 7. Security & Privacy

### 7.1 Cross-Tenant Propagation

When trace context crosses organizational boundaries (Agent A at Company X → Agent B at Company Y):

- **trace-id MUST be preserved** (needed for distributed debugging)
- **baggage MUST be stripped** (may contain internal PII)
- **tracestate MAY be preserved** (vendor-specific metadata)
- **deeparchi=br:1 entry MUST be added** (identifies bridge crossing)

### 7.2 Privacy Preserving Mode

For privacy-sensitive deployments:

```
┌─────────────────────────────────────────────────────┐
│  Privacy Mode (PP) flag in tracestate               │
│  tracestate: deeparchi=br:1;pp                     │
│                                                     │
│  When PP=1:                                         │
│  - trace-id: RETAIN (needed for chain)              │
│  - span-id:  REGENERATE at each boundary            │
│  - baggage:  STRIP entirely                         │
│  - span attrs: LIMIT to protocol-level fields only  │
│  - tool arguments: OMIT (may contain PII)            │
└─────────────────────────────────────────────────────┘
```

### 7.3 Access Control

At each bridge boundary, the admission-control checkpoint (Section 6.2) verifies:
1. Caller is authorized to invoke the target tool/agent
2. Bridge is not being used for trace-injection attacks
3. Rate limits are enforced per-trace-id

---

## 8. Implementation Guidance

### 8.1 Minimum Viable Implementation (~50 lines)

```go
// Bridge: A2A metadata → MCP _meta
func BridgeA2AToMCP(a2aMeta map[string]any) map[string]any {
    tc, ok := a2aMeta["https://deeparchi.ai/extensions/trace-context/v1"]
    if !ok {
        return nil // No trace context; start new trace
    }
    tcMap := tc.(map[string]any)
    newSpanID := generateSpanID()
    tcMap["traceparent"] = updateSpanID(tcMap["traceparent"].(string), newSpanID)
    // Inject deeparchi=br:1 into tracestate
    tcMap["tracestate"] = appendTracestate(tcMap["tracestate"], "deeparchi=br:1")
    return tcMap
}
```

### 8.2 SDK-Friendly: Middleware Pattern

```go
// A2A middleware: inject trace context into outgoing MCP calls
func TraceBridgeMiddleware(next MCPHandler) MCPHandler {
    return func(ctx context.Context, req *MCPRequest) (*MCPResponse, error) {
        if tc := extractFromA2AContext(ctx); tc != nil {
            req.Params.Meta["traceparent"] = tc.Traceparent
            req.Params.Meta["tracestate"] = tc.Tracestate
        }
        return next(ctx, req)
    }
}
```

### 8.3 Testing Vectors

```
TEST BR-1: A2A→MCP propagation
  GIVEN: A2A message with metadata.traceparent = "00-aaa...-bbb...-01"
  WHEN:  Bridge to MCP tools/call
  THEN:  params._meta.traceparent.trace-id = "aaa..." (same)
         params._meta.traceparent.span-id != "bbb..." (new span)
         params._meta.tracestate contains "deeparchi=br:1"

TEST BR-2: MCP→A2A propagation
  GIVEN: MCP tools/call with _meta.traceparent = "00-ccc...-ddd...-01"
  WHEN:  Bridge to A2A message
  THEN:  metadata[extension-uri].traceparent.trace-id = "ccc..." (same)
         metadata[extension-uri].traceparent.span-id != "ddd..." (new span)

TEST BR-3: Bridge chaining (A2A→MCP→A2A)
  GIVEN: A2A message → MCP → A2A message
  THEN:  All three share same trace-id
         Each boundary generates new span-id
         tracestate has "deeparchi=br:1" exactly once

TEST BR-4: Privacy mode
  GIVEN: A2A message with baggage = "user_id=123"
  WHEN:  PP flag set
  THEN:  Bridge strips baggage, regenerates span-id
```

---

## 9. Relationship to Existing Standards

| Standard | Relationship |
|----------|-------------|
| W3C Trace Context Level 1 | Bridge uses as canonical format |
| W3C Trace Context Level 2 | Forward-compatible (version auto-negotiation) |
| OpenTelemetry | Bridge produces OTel-compatible spans |
| MCP Audit Record SEP (#3004) | Bridge adds trace context to audit records |
| A2A Extensions | Bridge uses native extension mechanism |
| MCP _meta | Bridge uses reserved trace keys |

This specification introduces **no new protocol**. It occupies existing extension points and defines canonical mapping rules.

---

## 10. Versioning

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-07-03 | Initial working draft: A2A↔MCP bidirectional mapping, audit trail semantics, SMF analogy, privacy mode |
| planned 0.2 | TBD | Add gRPC transport binding, WebSocket support, test vectors as conformance suite |

---

*DeepArchi · 深度架构*
