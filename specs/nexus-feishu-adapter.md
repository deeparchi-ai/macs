# Nexus Feishu Adapter — Design Spec

**Status:** Draft (v0.1)
**Date:** 2026-08-03
**Author:** kuangmi (kuangmi@deeparchi.com.cn)
**Subsystem:** §8 Nexus (VTAM lineage)
**Companion repo:** [macs-nexus-go](https://github.com/deeparchi-ai/macs-nexus-go)
**Related:** [Agent Chat Governance Framework v1.0](/mnt/c/Users/kuang/DeepArchi-Vault/02-多Agent架构/Agent群聊发言治理框架-v1.md), [A2A Protocol](https://a2a-protocol.org)

---

## Abstract

Nexus currently resolves agent identities (LU names) to transports with a
priority order (gRPC > HTTP > WebSocket > MCP > Feishu) — but the Feishu
transport is a placeholder constant with no implementation. This spec defines
the **Feishu adapter**: the component that turns Feishu IM events (group
messages, @mentions, threads, attachments) into MACS-routable work, and turns
agent results back into Feishu messages. It is the interaction surface for the
"Feishu-native MACS deployment" — the bridge between Feishu's human
collaboration plane and MACS's agent governance plane.

## Problem

1. **No unified routing layer for Feishu.** Each agent today connects to Feishu
   through its own gateway (Hermes/OpenClaw) with its own App ID. There is no
   single place that answers "who should handle this @mention?"
2. **Governance is manual.** The chat-layer model (L0–L3) and the permission
   matrix (ALLOWED / MENTION_ONLY / ON_DEMAND / FORBIDDEN) live in config
   files and SOUL.md documents. Nothing enforces them programmatically at the
   message boundary.
3. **@mention → agent mapping is implicit.** A message that @mentions
   `cm-deepsight` should be routed to the deepsight agent's A2A endpoint, not
   to whichever bot happens to be listening.
4. **No audit point.** Every message an agent sends into a Feishu group is a
   governance event. Today there is no single interception point for
   Chronicle (audit) or Sanctum (policy) to observe it.

## Mainframe Analogy

| z/OS | MACS | Feishu adapter |
|------|------|----------------|
| VTAM application = LU name | Agent = LU name | Feishu bot open_id = LU alias |
| VTAM session | A2A task | Feishu chat (oc_xxx) = session |
| Session management (SESMGR) | Nexus router | Adapter routes chat events to LU |
| SNA RU (request unit) | A2A message | Feishu message (om_xxx) |
| LU-to-LU session establishment | Route(lu) | @mention → resolve LU → forward |

VTAM's core trick: applications talk to *names*, not wires. The Feishu adapter
extends this by registering Feishu bot identities as **aliases** of LU names —
a bot open_id is just another way to reach the same agent, with Feishu as the
transport.

## Design

### Data Model (Go)

```go
package feishu

// Event is a normalized Feishu event, independent of the Feishu API shape.
type Event struct {
    EventID   string      // dedup key (uuid)
    ChatID    string      // oc_xxx
    ChatLayer string      // "L0".."L3" — from governance framework
    Sender    string      // sender open_id
    SenderLU  vtam.LUName // resolved agent LU ("" if human)
    MessageID string      // om_xxx
    ThreadID  string      // omt_xxx (optional)
    Text      string      // plain text content
    Mentions  []vtam.LUName // @mentioned agents, resolved to LU names
    Attachments []Attachment
    Raw       json.RawMessage // original event payload (for Chronicle)
}

// Attachment describes a file/image in the message.
type Attachment struct {
    Kind   string // "image" | "file" | "audio" | "video"
    FileKey string // feishu file_key, downloadable via API
}

// Message is an outgoing Feishu message.
type Message struct {
    ChatID   string
    ReplyTo  string // om_xxx — reply to a specific message (thread support)
    Text     string
    Mentions []vtam.LUName // resolved to open_ids before send
    Files    []string      // local paths, uploaded via im:resource
}

// Adapter is the Nexus Feishu transport implementation.
type Adapter struct {
    router   *vtam.Router
    botLU    map[string]vtam.LUName // feishu bot open_id -> agent LU
    openID   map[string]vtam.LUName // human open_id -> agent LU ("" if human)
    policy   *Policy
    sink     EventSink // delivers normalized events to MACS (Nexus core)
}

// EventSink is the core-facing interface. Nexus routes the event to the
// target agent's best transport; if no transport is available, the event is
// dropped with an audit record.
type EventSink interface {
    Route(evt Event) error
}

// Policy encodes the governance matrix at the message boundary.
type Policy struct {
    // ChatLayer returns the layer of a chat id (L0-L3).
    ChatLayer func(chatID string) (string, error)
    // Allowed checks whether agent lu may speak in chat.
    Allowed func(lu vtam.LUName, layer string, isMention bool) bool
    // DenyReasons returns why a message was blocked (for Chronicle).
    DenyReasons []string
}
```

### Algorithm

**Ingress (Feishu → MACS):**

1. Receive event (WebSocket long-connection or webhook callback).
2. Dedup by `EventID` (idempotency key).
3. Normalize: extract chat_id, sender, mentions, text, attachments → `Event`.
4. Resolve mentions: each `<at user_id="ou_xxx">` → look up bot registry
   (`botLU`) → if the mentioned id maps to an agent LU, append to `Mentions`.
5. Policy gate: consult `Policy.Allowed(lu, layer, isMention)` for the target
   agent (or the sender, for proactive messages). Denied → record in Chronicle,
   drop silently (governance rule: 真静默 = 零消息).
6. Route: `sink.Route(evt)` → Nexus resolves the best transport for the
   target LU (Feishu itself, A2A gRPC, MCP, ...). If target is another agent
   with a better transport, the event crosses the bridge into A2A.
7. Audit: every step (received / allowed / denied / routed) appends to
   Chronicle with the original event payload.

**Egress (MACS → Feishu):**

1. Agent produces a result message + optional local file paths.
2. `Message` built with `ReplyTo` set to the triggering message (thread
   continuity).
3. Mentions resolved: LU names → open_ids → `<at user_id="ou_xxx">` with
   `--text` mode (markdown mode strips `<at>` tags — known pitfall).
4. Files uploaded via `im:resource` (bot token), then attached.
5. Sent via `im.message.create` / `im.message.reply`.
6. `MessageID` recorded in Chronicle for trace continuity.

### Integration Points

| Component | Role in this design |
|-----------|--------------------|
| Nexus (vtam) | `TransportFeishu` registration; alias resolution bot open_id → LU |
| Governance framework | `Policy.ChatLayer` + `Policy.Allowed` — the L0–L3 matrix |
| A2A protocol | Bridge: Feishu event → A2A `tasks/send` when target agent prefers A2A |
| Sanctum | Auth check on sender open_id → known principal; trust scoring hooks |
| Chronicle | Event log: received/denied/routed/sent with raw payloads |
| Seal | Verify bot signatures on webhook callbacks (if webhook mode) |
| Gauge | Metrics: events/sec, deny rate, routing latency |

### Deployment Topology

```
Feishu IM
   │  WebSocket / webhook events
   ▼
┌──────────────────────────────┐
│ Nexus (macs-nexus-go)        │
│  └─ feishu.Adapter           │  ← this spec
│      ├─ Policy (L0-L3 gate)  │
│      └─ router.Route(LU)     │
└──────────┬───────────────────┘
           │ EventSink
           ▼
    A2A / MCP transport        → target agent (Hermes profile, do-xxx, ...)
```

Each agent keeps its own Feishu bot identity (App ID) for identity separation;
the adapter does **not** multiplex one bot across agents. What the adapter adds
is a routing + policy layer *in front of* the bots: the first bot to receive a
message consults Nexus, which decides whether it should handle it or forward
via A2A to a better-suited agent.

## Implementation Plan

**Phase 1 — Data model + policy (≈250 lines, pure Go, no Feishu API):**
- `Event`, `Message`, `Attachment`, `Adapter` types
- `Policy` with layer resolution and allowed() checks
- Unit tests for mention resolution and policy matrix (table-driven)

**Phase 2 — Ingress normalization (≈300 lines + API client):**
- Feishu event subscription parsing (im.message.receive_v1)
- Dedup by EventID, mention extraction (`<at user_id="ou_...">` regex/parse)
- Chronicle sink hooks (event log)

**Phase 3 — Egress + bridge (≈300 lines):**
- Message send/reply via lark-cli-compatible HTTP API (bot identity)
- File upload (`im:resource`) and attachment
- A2A bridge: route events to remote agents via their A2A endpoint

**Non-Goals:**
- No multi-tenant SaaS: adapter assumes one organization's Feishu tenant
- No web apps: Feishu app ecosystem (Miaoda/Spark) covers that plane
- No approval flows: es-reimbursement's native Feishu approval remains separate
- No new security posture: inherits QM-style per-scope isolation from the
  governance framework; the adapter is a boundary, not a trust anchor

## Risks

| Risk | Mitigation |
|------|-----------|
| Event storms (group spam) | Rate limiting at adapter; Gauge metrics; Policy gate |
| Mention resolution ambiguity | Explicit registry: open_id → LU is 1:1, no fuzzy match |
| Policy too strict → agents go silent | Governance rule: MENTION_ONLY default; ALLOWED explicit |
| One bot per agent multiplies maintenance | Adapter is the single integration point; bots stay thin |
