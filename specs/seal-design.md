# MACS §10 — Seal: Identity Registry & Cryptographic Binding

> **DeepArchi · 邝谧**
> *Working Draft v0.1 — Pre-implementation design for the identity and cryptography subsystem.*
> IBM lineage: **ICSF** (Integrated Cryptographic Service Facility) + **RACF** user registry

## Abstract

Seal is the MACS identity subsystem that manages agent registration, certificate lifecycle (rotation and revocation), and cryptographic binding of agent output. It answers "Who are you?" while Sanctum §3 answers "What are you allowed to do?" — a clean separation preventing identity management from entangling with access control.

## Problem

In a multi-agent system where agents delegate to sub-agents and call across trust boundaries, every participant must be cryptographically identifiable. Without a central identity registry: (a) an agent cannot verify that a sub-agent's output genuinely came from that sub-agent, (b) a revoked or compromised agent can continue operating undetected, and (c) certificate rotation happens ad-hoc with no coordinated lifecycle.

Existing solutions conflate identity with authorization (OAuth scopes, IAM roles). This creates tight coupling: rotating a certificate requires updating every access policy that references it. MACS separates these concerns: Seal owns identity (LU name, public key hash, trust root, status), and Sanctum owns authorization (tool profiles, access levels, pathing rules). When a certificate rotates, only Seal is updated; Sanctum continues to reference the stable LU name.

The subsystem also provides the foundation for **non-repudiation of agent output**. When an agent makes a decision, Seal binds that output to the agent's identity via a JWS (JSON Web Signature) — allowing downstream consumers to verify provenance without trusting the transport.

## Mainframe Analogy

IBM z/OS **ICSF (Integrated Cryptographic Service Facility)** provides hardware-accelerated cryptographic operations and key management for the mainframe. It manages digital certificates, performs encryption/decryption, and generates digital signatures. Seal adopts this model at the application layer: agent-level certificate management, identity registration with trust-root pinning, and output signing. The RACF user registry (distinct from RACF's access-control role) provides the model for the identity directory — agent identities with status lifecycle, expiration, and revocation.

## Data Model

```go
// AgentStatus is the lifecycle state of an agent identity.
type AgentStatus int

const (
    StatusActive   AgentStatus = iota // normal operation
    StatusRotating                    // certificate rotation in progress
    StatusRevoked                     // permanently deactivated
)

// AgentIdentity represents a registered agent in the MACS ecosystem.
type AgentIdentity struct {
    LUName        string      // Logical Unit name — stable identifier
    AgentCardURL  string      // A2A Agent Card URL
    PublicKeyHash string      // SHA256 of the agent's public key
    TrustRoot     string      // pinned trust root for this agent
    Status        AgentStatus
    CreatedAt     time.Time
    ExpiresAt     time.Time
}

// IdentityRegistry manages agent identity lifecycle.
type IdentityRegistry struct {
    mu         sync.RWMutex
    identities map[string]*AgentIdentity // keyed by LUName
}
```

**Key methods:**
- `Register(id *AgentIdentity) error` — register a new agent; errors on duplicate LUName
- `Lookup(luName string) (*AgentIdentity, bool)` — find by LU name
- `Revoke(luName, reason string) error` — permanently deactivate; errors if already revoked
- `ListActive() []*AgentIdentity` — all non-revoked agents
- `ListByStatus(status AgentStatus) []*AgentIdentity` — filter by lifecycle state

## Algorithm

### 1. Agent Registration
```
Step 1: Receiving agent presents LUName + AgentCardURL + PublicKeyHash + TrustRoot
Step 2: Validate LUName is non-empty and unique
Step 3: Validate AgentCardURL is a well-formed A2A card endpoint
Step 4: Validate PublicKeyHash matches the SHA256 of the presented public key
Step 5: Validate TrustRoot is a known root CA (from PARMLIB)
Step 6: Create AgentIdentity{Status: Active, CreatedAt: now, ExpiresAt: now + defaultTTL}
Step 7: Store in registry map keyed by LUName
Step 8: Emit "agent.registered" event via Relay §11
```

### 2. Certificate Rotation (StatusRotating → StatusActive)
```
Step 1: Agent presents new PublicKeyHash + proof-of-possession of new key
Step 2: Seal verifies proof against current registered key
Step 3: Set Status → Rotating (new requests temporarily deferred)
Step 4: Update PublicKeyHash + TrustRoot to new values
Step 5: Set Status → Active
Step 6: Emit "agent.rotated" event via Relay §11
```

### 3. Revocation
```
Step 1: Caller (Warden §12 or admin Console §14) requests revocation with reason
Step 2: Verify agent exists and is not already revoked
Step 3: Set Status → Revoked
Step 4: Emit "agent.revoked" event via Relay §11
Step 5: Sanctum §3 receives event, invalidates all access grants for this LUName
Step 6: VTAM §8 removes the agent from its routing table
```

### 4. Output Signing (a2acrypto integration)
```
Step 1: Agent produces output D (decision, tool result, or message)
Step 2: Agent calls Seal.Sign(D, luName) → JWS compact serialization
Step 3: Seal looks up agent's key material via LUName
Step 4: Produces JWS header {alg, kid, typ: "macs-agent-output"}
Step 5: Signs payload with agent's private key
Step 6: Consumer calls Seal.Verify(jws) → (payload, identity, error)
```

## Integration Points

| Consumed by Seal | Purpose |
|------|------|
| VTAM §8 | LU name validation and routing table updates |
| A2A Agent Card protocol | AgentCardURL validation and trust root discovery |
| PARMLIB | Trusted root CA list, default certificate TTL |

| Consumed from Seal | By | Purpose |
|------|------|------|
| `IdentityRegistry.Lookup()` | Sanctum §3 | Resolve LUName to identity during access checks |
| `IdentityRegistry.Lookup()` | VTAM §8 | Route requests to verified agent endpoints |
| `IdentityRegistry.ListActive()` | Console §14 | Display registered agents dashboard |
| `agent.revoked` event | Relay §11 → Sanctum, VTAM, Warden | Propagate revocation cluster-wide |
| JWS output signatures | A2A consumers | Non-repudiation of agent decisions |

## Implementation Plan

| Phase | Lines | Scope |
|------|:-----:|------|
| Phase 1 | ~100 | AgentIdentity, AgentStatus, IdentityRegistry (Register/Lookup/Revoke) |
| Phase 2 | ~60 | ListActive, ListByStatus, Count, expiration check |
| Phase 3 | ~80 | Certificate rotation workflow (StatusRotating state machine) |
| Phase 4 | ~120 | JWS signing/verification, a2acrypto integration (#368) |
| **Total** | **~360** | |

## Non-Goals

- **Access control enforcement** — Seal identifies agents; Sanctum §3 decides what they can do.
- **Key generation and storage** — Agents generate their own keys; Seal stores only the public key hash.
- **Network-level TLS** — Transport security is VTAM §8 territory. Seal handles application-layer identity binding.
- **Federated identity (OIDC/SAML)** — MACS agents use Seal-native identity; external identity federation is out of scope for v0.1.
- **Hardware security module (HSM) integration** — Seal operates at the application layer; ICSF's HSM role is acknowledged but not directly replicated.
