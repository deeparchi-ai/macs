# MACS §11 — Relay: Cluster State & Event Broadcast

> **DeepArchi · 邝谧**
> *Working Draft v0.1 — Pre-implementation design for the cluster communication subsystem.*
> IBM lineage: **XCF** (Cross-system Coupling Facility)

## Abstract

Relay is the MACS inter-agent communication backbone, providing cluster membership with heartbeat-based liveness, typed publish/subscribe event broadcast, group communication with atomic multicast, and shared state with TTL-based expiration. It enables agents in separate processes to coordinate without direct RPC coupling.

## Problem

MACS agents run as separate processes — potentially on separate hosts. They need to: (a) know which peer agents are alive (membership), (b) receive typed events from other agents without polling (pub/sub), (c) coordinate as named groups (e.g., "all XVal models"), and (d) share transient coordination state without a database (shared state). Without a common communication layer, every agent implements ad-hoc discovery and messaging.

Existing solutions like etcd or Consul are designed for infrastructure coordination (leader election, service discovery) — heavyweight for in-process agent communication. NATS and Redis Pub/Sub handle messaging but lack the group-communication semantics (join/leave/send-to-group) and TTL-based shared state that multi-agent workflows need. Relay fills this gap with a purpose-built, in-process communication layer that mirrors XCF's role in z/OS: coupling separate address spaces through shared facilities.

The pub/sub system is particularly critical because it decouples event producers from consumers. When Cadence §6 completes a job, it publishes `job.complete` without knowing who listens. Warden §12 subscribes to detect failed jobs; Console §14 subscribes to update its dashboard; Cadence itself listens for `job.complete` to trigger DAG successors. Adding a new consumer requires no changes to the producer.

## Mainframe Analogy

IBM z/OS **XCF (Cross-system Coupling Facility)** enables communication between applications running in different address spaces or LPARs. It provides group services (membership with heartbeat), signaling (event delivery), and shared coupling-facility structures. Relay adopts all three: `Cluster` mirrors XCF group membership with heartbeat-based liveness detection; `Broadcast` mirrors XCF signaling with typed event pub/sub; `SharedState` mirrors XCF coupling-facility cache structures with TTL expiration. The `GroupComm` abstraction mirrors XCF's group communication — members join/leave named groups and receive atomic multicasts.

## Data Model

```go
// ── Membership ──

type MemberStatus int
const (
    MemberOnline    MemberStatus = iota
    MemberOffline
    MemberDegraded
)

type ClusterMember struct {
    ID            string
    LUName        string
    Address       string
    Status        MemberStatus
    LastHeartbeat time.Time
    JoinedAt      time.Time
}

type Cluster struct {
    mu      sync.RWMutex
    members map[string]*ClusterMember
}

// ── Pub/Sub ──

type Event struct {
    Type      string
    Source    string // agent LU name
    Timestamp time.Time
    Payload   interface{}
}

type Subscription struct {
    Type    string
    Channel chan Event
}

type Broadcast struct {
    mu            sync.RWMutex
    subscriptions map[string][]*Subscription
}

// ── Group Communication ──

type GroupComm struct {
    mu     sync.RWMutex
    groups map[string]map[string]bool
}

// ── Shared State ──

type SharedState struct {
    mu    sync.RWMutex
    store map[string]*stateEntry
}

type stateEntry struct {
    Value     string
    ExpiresAt time.Time
}
```

**Key methods:**

**Cluster:** `Join`, `Leave`, `Heartbeat`, `GetMember`, `ListOnline`, `DetectStale(timeout)`

**Broadcast:** `Publish(event) int`, `Subscribe(eventType) *Subscription`, `Unsubscribe(sub)`

**GroupComm:** `JoinGroup/LeaveGroup(groupName, memberID)`, `SendToGroup(groupName, event, bcast)`

**SharedState:** `Put(key, value, ttl)`, `Get(key)`, `Delete(key)`, `List(prefix)`, `CleanExpired()`

## Algorithm

### 1. Heartbeat-Based Liveness Detection
```
Step 1: Each agent calls Cluster.Heartbeat(id) every 5s (configurable)
Step 2: Cluster updates LastHeartbeat to now, promotes Offline→Online if needed
Step 3: Cluster.DetectStale(timeout) runs on a 10s timer
Step 4: Any member with LastHeartbeat older than timeout → Status = MemberOffline
Step 5: Stale members are returned to caller (typically Warden §12)
Step 6: Warden broadcasts "member.offline" event for recovery policy evaluation
```

### 2. Event Broadcast Flow
```
Producer: bcast.Publish(Event{Type: "job.complete", Source: "cadence", Payload: jobID})
        → finds all Subscription with Type="job.complete"
        → non-blocking send to each subscriber channel (buffer=100)
        → returns count of delivered events

Consumer: sub := bcast.Subscribe("job.complete")
        → receives Event on sub.Channel in a goroutine
        → processes event, then waits for next
```

### 3. Group Communication with Atomic Multicast
```
Step 1: XVal models call GroupComm.JoinGroup("xval-models", "xval-claude")
Step 2: Orchestrator calls SendToGroup("xval-models", event, bcast)
Step 3: GroupComm iterates group members, publishes to each via Broadcast
Step 4: All group members receive the same event (atomic multicast semantics)
```

### 4. Shared State with TTL
```
Step 1: Agent A: SharedState.Put("lock:task-42", agentA_ID, 30*time.Second)
Step 2: Agent B: SharedState.Get("lock:task-42") → (agentA_ID, true)
Step 3: After 30s: SharedState.Get("lock:task-42") → ("", false) — expired
Step 4: Cleaner goroutine: SharedState.CleanExpired() runs every 60s, removes stale entries
Step 5: List("lock:") → all non-expired lock keys — used for coordination dashboards
```

## Integration Points

| Consumed by Relay | Purpose |
|------|------|
| All MACS subsystems | Publish events for cluster-wide consumption |
| Pulse §13 | Publish heartbeat events for self-health monitoring |

| Consumed from Relay | By | Purpose |
|------|------|------|
| `Broadcast.Subscribe("job.complete")` | Cadence §6 | Trigger DAG successor jobs |
| `Broadcast.Subscribe("job.failed")` | Warden §12 | Crash escalation |
| `Broadcast.Subscribe("agent.*")` | Console §14 | Real-time dashboard updates |
| `Broadcast.Subscribe("member.offline")` | Warden §12 | Trigger recovery plans |
| `Cluster.ListOnline()` | VTAM §8 | Agent routing table |
| `Cluster.DetectStale()` | Warden §12 | Crash detection input |
| `SharedState.Get/Put` | All agents | Distributed coordination primitives |
| `GroupComm.SendToGroup()` | XVal §5 | Cross-model coordination |

## Implementation Plan

| Phase | Lines | Scope |
|------|:-----:|------|
| Phase 1 | ~120 | Event, Subscription, Broadcast (Publish/Subscribe/Unsubscribe) |
| Phase 2 | ~100 | ClusterMember, Cluster, MemberStatus, heartbeat + DetectStale |
| Phase 3 | ~80 | GroupComm (JoinGroup/LeaveGroup/SendToGroup) |
| Phase 4 | ~100 | SharedState (Put/Get/Delete/List/CleanExpired), TTL semantics |
| Phase 5 | ~50 | Integration with Warden crash detection, Console dashboard |
| **Total** | **~450** | |

## Non-Goals

- **Cross-host networking** — Relay provides in-process abstractions; actual wire transport is VTAM §8's concern. Relay assumes VTAM handles the remote delivery.
- **Persistence** — SharedState is in-memory only. Durable coordination state belongs to Chronicle §4 or external storage.
- **Leader election** — Relay provides membership and pub/sub; leader election (if needed) is built on top by consumers.
- **Message ordering guarantees** — Broadcast is best-effort (non-blocking send). Total ordering requires a consumer-side sequence number layer.
- **WAN/cluster federation** — Single-cluster scope. Multi-datacenter XCF coupling facility replication is a future concern.
