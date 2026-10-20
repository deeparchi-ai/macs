# Cross-Protocol Trace Context Bridge

## A2A ↔ MCP Trace Context Propagation Specification v0.3.1

> **DeepArchi · 邝谧**  
> 2026-07-03 · Working Draft · last revised 2026-10-21

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
- A2A's bindings differ in header semantics: JSON-RPC and HTTP+JSON carry HTTP headers, gRPC carries its own metadata, and custom bindings (for example WebSocket) may have neither
- Payload-level embedding survives queueing, batching, and retry

A payload-level bridge reaches transports that have no usable header channel. Where a binding does provide headers, those remain the primary carrier (§4.4).

### 1.3 The SMF Analogy

IBM's SMF (System Management Facility) solved a similar problem in 1971: how to trace a transaction across CICS regions, DB2 calls, and MQ puts without a common protocol. The answer: **SMF type 110 records** with a shared **URID (Unit of Recovery ID)** that propagated through every boundary.

This specification applies the same principle: W3C `trace-id` is the URID.

---

## 2. Canonical Trace Context

The bridge uses the W3C Trace Context `traceparent` / `tracestate` formats at `version: 00` — the only version either Trace Context Level 1 or Level 2 specifies. Implementations MUST parse version `00` strictly and SHOULD parse higher versions positionally over the first 55 characters (W3C §3.2.4), so that a future revision does not break the chain; version `ff` is forbidden, as are all-zero trace-ids and parent-ids.

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

W3C Trace Context §3.5 recommends placing a newly added or modified `tracestate` entry at the beginning (left) of the list; size truncation removes entries from the end, so the left position is also the one that survives longest. The bridge therefore prepends `deeparchi=br:1`.

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

| A2A operation | OTel span name | Span kind |
|---------------|----------------|-----------|
| `SendMessage`, `SendStreamingMessage` | `SendMessage`, `SendStreamingMessage` | CLIENT |
| `GetTask`, `CancelTask`, `SubscribeToTask` | same as the method name | CLIENT |
| Request handling | same as the method name | SERVER |

Span names follow the in-flight OpenTelemetry A2A semantic conventions (`open-telemetry/semantic-conventions-genai`, PR #195), which prescribe `{a2a.method.name}` and carry the agent identity as the `gen_ai.agent.name` attribute rather than inside the span name.

Earlier drafts of this document used the pre-1.0 A2A method names (`tasks/send`, `tasks/get`, `message/send`) and embedded the agent name in the span name. Both are withdrawn: A2A 1.0.1 methods are `SendMessage`, `SendStreamingMessage`, `GetTask`, `ListTasks`, `CancelTask`, `SubscribeToTask` and the task push-notification configuration calls.

---

## 4. MCP Binding

### 4.1 _meta Embedding

MCP reserves `traceparent`, `tracestate`, and `baggage` as unprefixed keys in `params._meta`. The MCP specification 2026-07-28 defines them normatively (§ `_meta`, "OpenTelemetry trace context"):

> As an exception to the prefix requirement above, the keys `traceparent`, `tracestate`, and `baggage` are reserved for OpenTelemetry trace context propagation. When present, their values MUST follow W3C Trace Context and W3C Baggage formats respectively.

Citation: <https://modelcontextprotocol.io/specification/2026-07-28/basic> (§ `_meta`). Earlier MCP revisions (2025-06-18, 2025-11-25) did not define these keys at all; the reservation entered the specification with the 2026-07-28 revision. Consequently the bridge needs no MCP-side extension URI — it writes the reserved keys directly, and the field formats defined in §2.1 already satisfy the MUST above.

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

Per the OpenTelemetry semantic conventions for MCP (merged as `open-telemetry/semantic-conventions` PR #2083 on 2026-01-12; now maintained in `open-telemetry/semantic-conventions-genai` → `docs/gen-ai/mcp.md`). Span names SHOULD be `{mcp.method.name} {target}`, where `target` matches `gen_ai.tool.name` or `gen_ai.prompt.name` when a low-cardinality target exists, and the bare method name otherwise. Resource URIs SHOULD NOT be part of the default span name because of cardinality.

| MCP method | OTel span name | Span type |
|------------|----------------|-----------|
| `tools/call` | `tools/call {gen_ai.tool.name}` | `mcp.client` (CLIENT) |
| `tools/list` | `tools/list` | `mcp.client` (CLIENT) |
| `resources/read` | `resources/read` | `mcp.client` (CLIENT) |

The conventions also define `mcp.server` (SERVER) spans for the receiving side, and note that an MCP tool-execution span is compatible with the GenAI `execute_tool` span.

### 4.3 Notification Handling

MCP notifications (messages without `id`) MUST propagate trace context but MUST NOT create new spans. Observations are attached to the parent span.

### 4.4 Carrier Coverage on the A2A Side

This extension embeds trace context in message `metadata`. Not every A2A operation has that field. Verified against `specification/a2a.proto` at tag `v1.0.1`:

| Operation | Request message | `metadata` field |
|-----------|-----------------|------------------|
| SendMessage / SendStreamingMessage | `SendMessageRequest` | yes (`metadata = 4`) |
| CancelTask | `CancelTaskRequest` | yes (`metadata = 3`) |
| GetTask | `GetTaskRequest` | **no** (`tenant`, `id`, `history_length`) |
| SubscribeToTask | `SubscribeToTaskRequest` | **no** (`tenant`, `id`); the GET binding has no body |
| Push-notification delivery (agent → webhook) | none; body is a `StreamResponse` | not applicable |

A metadata-only carrier therefore cannot carry context through task polling, resubscription, or push callbacks — that is, through most of a long-running task's life. Implementations MUST:

1. Treat transport-level context as the primary carrier: `traceparent` / `tracestate` / `baggage` as HTTP headers on HTTP bindings, and as gRPC metadata on gRPC.
2. Treat message `metadata` as the fallback carrier, for custom bindings without a header channel.
3. When both are present, the transport header wins. The two sources MUST NOT be merged or reconciled field by field.
4. Agents SHOULD send `traceparent` on push-notification POSTs so callbacks join the originating trace.
5. `GetTask` and `SubscribeToTask` MUST NOT be treated as children of the originating execution span. Where causal linkage is required, express it as a span link rather than a parent-child relation.

---

## 5. Bridge Behavior

### 5.0 Span and context responsibilities

The bridge moves propagation context between carriers. It does not own span topology: span creation, naming, kind, activation and lifetime belong to the instrumentation of the host, and this specification does not require any particular receiving-side span to exist.

Three rules apply to both directions:

- **Parent selection.** When an outbound span is created, its parent MUST be selected from the Context of the local operation that initiates the outbound call. An existing local operation Context MUST NOT be replaced by the extracted remote Context merely because the protocol changes. If the initiating operation has no local span, the validated extracted remote Context MAY be used directly as parent.
- **Full Context, not a bare span-id.** A W3C `traceparent` is not a parent by itself: OpenTelemetry requires a full `Context` ("The API MUST NOT accept a Span or SpanContext as parent, only a full Context"), so trace-id, `tracestate`, trace flags and remote-ness travel with it.
- **Propagation-only mode.** If no outbound span is created, the accepted inbound `traceparent` and `tracestate` MUST be propagated unchanged. W3C §3.4: "If the value of the traceparent field wasn't changed before propagation, tracestate MUST NOT be modified as well" — therefore the `deeparchi=br:1` marker MUST NOT be added in this mode.

> On span kind: the SERVER/CLIENT chains in §5.1 and §5.2 illustrate a fully instrumented request–response exchange. Deferred or queue-based processing may use CONSUMER/PRODUCER instead; the rules above are independent of kind.

> Implementation note — a host that runs an OpenTelemetry SDK MUST inject the `SpanContext` of the span the SDK created; the span-id comes from the SDK's ID generator, not from the bridge. Bridge-generated IDs (`NewSpanID` / `UpdateSpanID` in the reference implementation) exist for hosts that do not run an SDK, and MUST NOT be used to override an SDK-created span.

### 5.1 A2A → MCP (Inbound Bridge)

When an A2A agent receives a message containing the trace context extension and subsequently calls an MCP tool:

```
INPUT:   A2A request carrying trace context — transport headers (primary) or message metadata (fallback)
OUTPUT:  MCP tools/call with params._meta.traceparent
```

**Algorithm:**

```
1. EXTRACT the inbound propagation context — from the transport headers first,
   then from A2A message.metadata as fallback (§4.4). Validate the
   traceparent; an all-zero trace-id or parent-id is invalid and MUST be
   treated as absent (W3C §3.2.2.3 / §3.2.2.4).
2. OBTAIN the Context of the operation initiating the MCP call — normally the
   handler processing this A2A message. If that handler has a span, it is the
   parent; if it has none, use the validated extracted remote Context.
3. CREATE the outbound tools/call span from that parent Context, or reuse an
   existing span for the same call. The receiving agent's own processing span,
   if any, is created by its handler, not by the bridge.
4. INJECT the resulting Context — the outbound span's actual SpanContext plus
   tracestate and baggage — into params._meta. Add "deeparchi=br:1" to
   tracestate only if traceparent is rewritten (§5.0).
5. SEND the tools/call.
```

**Span Chain** (fully instrumented example):

```
A2A Orchestrator Agent (SERVER, trace=t, span=s1)
  └── A2A message/send (CLIENT, trace=t, span=s2, parent=s1)
      │      A2A hop carries parent-id=s2
      └── A2A message/process (SERVER, trace=t, span=s3, parent=s2)   <- instrumentation-owned
          └── MCP tools/call web_search (CLIENT, trace=t, span=s4, parent=s3)
              └── Web Search Tool (SERVER, trace=t, span=s5, parent=s4)
```

The s3 span exists only if the receiving agent instruments its message handler. When it does not, step 2 falls back to the extracted remote Context and the MCP client span becomes a direct child of s2: one hop is lost from the tree, but the chain stays connected. A bridge that sets the outbound parent to the extracted span-id even when a local handler span exists is the case to avoid — it discards the local causal context that the instrumentation already recorded.

### 5.2 MCP → A2A (Outbound Bridge)

When an MCP server (or tool) delegates work back to an A2A agent:

```
INPUT:   MCP tools/call with params._meta.traceparent
OUTPUT:  A2A message with metadata[extension-uri].traceparent
```

**Algorithm:**

```
1. EXTRACT traceparent, tracestate and baggage from MCP params._meta (reserved
   keys; invalid values are treated as absent).
2. OBTAIN the Context of the operation initiating the A2A call — normally the
   tool handler's current span. If it has none, use the validated extracted
   remote Context.
3. CREATE or reuse the outbound a2a.message/send span from that Context.
4. INJECT its SpanContext plus tracestate and baggage into A2A
   message.metadata under the extension URI — and into transport headers when
   the binding provides them (§4.4) — adding "deeparchi=br:1" only if
   traceparent is rewritten (§5.0).
5. SET the A2A-Extensions header (HTTP transport).
6. SEND the message.
```

### 5.3 Bridge Chaining (Multi-Hop)

The bridge is idempotent across multiple hops:

```
A2A → MCP → A2A → MCP → Tool
```

Each boundary creates a new span (or reuses an existing one for the same outbound call); the trace-id is invariant. In propagation-only mode no span is created and the context is forwarded unchanged. The `deeparchi=br:1` tracestate entry signals "already bridged" — subsequent bridges MUST NOT re-wrap.

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
| W3C Trace Context (Level 1 and Level 2) | Bridge uses the `traceparent` / `tracestate` formats both levels specify (version `00`); higher versions are parsed positionally per §3.2.4 rather than rejected |
| OpenTelemetry | Bridge produces OTel-compatible spans; naming follows the A2A and MCP semantic conventions (§3.5, §4.2) |
| MCP Audit Record SEP (#3004) | Bridge adds trace context to audit records |
| A2A Extensions | Bridge uses native extension mechanism |
| MCP `_meta` (spec 2026-07-28) | Bridge uses the reserved `traceparent` / `tracestate` / `baggage` keys; W3C formats are a MUST on the MCP side |

This specification introduces **no new protocol**. It occupies existing extension points and defines canonical mapping rules.

---

## 10. Versioning

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-07-03 | Initial working draft: A2A↔MCP bidirectional mapping, audit trail semantics, SMF analogy, privacy mode |
| 0.1.1 | 2026-10-21 | Editorial correction: §4.1 now cites MCP specification 2026-07-28, where `traceparent`/`tracestate`/`baggage` are reserved `_meta` keys with a W3C-format MUST (the 2025-06-18 and 2025-11-25 revisions did not define them). No protocol change. |
| 0.2 | 2026-10-21 | New §4.4 carrier coverage: `GetTaskRequest` / `SubscribeToTaskRequest` have no `metadata` and push callbacks carry a `StreamResponse`, so transport headers are the primary carrier with message `metadata` as fallback and header-wins on conflict; §5.1 / §5.2 extraction order updated to match. Normative addition, breaking for implementations that assumed a metadata-only carrier. |
| 0.3 | 2026-10-21 | §5 rework: new §5.0 parent-selection rules (outbound parent comes from the local operation Context; the extracted remote Context is a fallback only), propagation-only mode, full-Context requirement, SDK ID-generator note; §5.1/§5.2 algorithms reordered to create-then-inject, no longer hand-generate span-ids, and extract from transport headers before message metadata; span chains marked as fully instrumented examples. §2.2 notes W3C tracestate ordering. |
| 0.3.1 | 2026-10-21 | Corrections against current sources: §3.5 updated to A2A 1.0.1 method names (`SendMessage`, `GetTask`, `CancelTask`, `SubscribeToTask` — the pre-1.0 `tasks/send` / `message/send` forms are withdrawn) and to the in-flight OTel A2A semconv naming `{a2a.method.name}` with the agent as `gen_ai.agent.name`; §4.2 cites the merged OTel MCP conventions (PR #2083, now in `semantic-conventions-genai`) and its `{mcp.method.name} {target}` rule; §1.2 and §2 corrected on A2A bindings and traceparent version handling (higher versions parsed positionally per W3C §3.2.4, `ff` and all-zero ids rejected); §1.2 no longer claims a payload carrier covers every transport. Editorial. |
| planned 0.4 | TBD | Add gRPC transport binding, WebSocket support, test vectors as conformance suite |

---

*DeepArchi · 深度架构*
