# Curator Skill Seeding — Design Spec

**Status:** Draft (v0.1)
**Date:** 2026-08-03
**Author:** kuangmi (kuangmi@deeparchi.com.cn)
**Subsystem:** §7 Curator (DFSMS lineage)
**Companion repo:** [macs-curator-go](https://github.com/deeparchi-ai/macs-curator-go)
**Inspired by:** [QM skill governance](https://github.com/yc-software/qm) — scope-owned skills, share-by-grant, admin-gated promotion, git-based skill packs
**Dependencies:** Sanctum §3 (trust scoring, v0.1 Go), Seal §10 (identity registry, v0.1 Go)

---

## Abstract

Curator currently manages *knowledge* (context chunks, tiered compression).
This spec extends it to manage *skills* — the executable knowledge agents
carry. QM's skill model (personal scope → share by grant → admin-gated
promotion → org skill pack) is a proven bottom-up market mechanism: anyone can
seed a skill in their own scope, proven skills get shared, validated skills
get promoted. MACS adopts this pattern with one key change: **permissions are
granted by agents to agents** (via Sanctum trust scoring), not by people to
people. This spec defines the skill lifecycle, the promotion pipeline, and the
Curator API extensions.

## Problem

1. **Skills are siloed.** Each agent has its own skill set (e.g. Hermes skills
   per profile). A skill that works well for one agent is invisible to others.
2. **No bottom-up discovery.** Curator's current model is top-down knowledge
   management. There is no path for "I made this skill, it works, others
   should see it."
3. **No trust signal.** When agent B wants to use agent A's skill, B has no
   way to know if A's skill is reliable. QM solves this with org hierarchy
   (admin grants); MACS needs an agent-native equivalent.
4. **No lifecycle.** Skills are created and abandoned. Nothing archives
   obsolete skills or promotes proven ones.

## Mainframe Analogy

| z/OS | MACS | Skill seeding |
|------|------|---------------|
| DFSMS management classes | Curator | Skill lifecycle policies |
| DFSMSdss backup/restore | Curator | Skill pack export/import |
| RACF profiles | Sanctum | Grant + trust scoring |
| RACF ownership | Seal | Skill owner identity |
| SMP/E (System Modification Program) | Curator promote | Admin-gated promotion to org pack |

SMP/E is the closest lineage: IBM shipped z/OS with base system + optional
feature packs, validated through SMP/E's service/validation gates before they
reached production LPARs. The skill promotion pipeline mirrors SMP/E: a skill
moves from personal (SMP/E local), to shared (SMP/E test), to promoted (SMP/E
production), each stage with validation gates.

## Design

### Skill Lifecycle (5 stages)

```
personal → shared → promoted → org-pack → archived
    ↑                                        ↓
    └────────── recall (re-seed) ←───────────┘
```

| Stage | Who can see | Who can use | Gate |
|-------|-------------|-------------|------|
| **Personal** | Owner agent only | Owner agent | None (zero friction — any agent can create) |
| **Shared** | Agents with grant | Grantees | Owner grants; Sanctum records grant |
| **Promoted** | All agents in org | All agents | Curator review: usage stats + trust score + owner signature (Seal) |
| **Org pack** | All agents | All agents | Pack is versioned, git-based; updates go through same pipeline |
| **Archived** | Read-only index | No one (recall allowed) | TTL / no usage / superseded |

### Data Model (Go)

```go
package skills

// Skill is an agent-executable procedure.
type Skill struct {
    ID          string     // hash of name+version (Seal-signed)
    Name        string     // e.g. "lark-im-reply"
    Version     string     // semver
    Owner       string     // agent LU name
    Stage       Stage      // personal/shared/promoted/org-pack/archived
    Summary     string     // what it does (for Curator recall)
    UsageCount  int        // invocations (Gauge source)
    SuccessRate float64    // 0..1 (Gauge source)
    TrustScore  float64    // 0..1 (Sanctum source)
    Signature   []byte     // Seal signature (owner identity)
    Body        string     // skill content (SKILL.md or reference)
    Tags        []string   // for recall/search
    CreatedAt   time.Time
    UpdatedAt   time.Time
}

// Stage is the lifecycle stage of a skill.
type Stage int

const (
    StagePersonal Stage = iota
    StageShared
    StagePromoted
    StageOrgPack
    StageArchived
)

// Grant is an agent-to-agent skill grant (Sanctum records it).
type Grant struct {
    SkillID   string
    Grantor   string // owner LU
    Grantee   string // receiving agent LU
    GrantedAt time.Time
    RevokedAt *time.Time
}

// PromotionPolicy defines when a shared skill may be promoted.
type PromotionPolicy struct {
    MinUsageCount   int     // e.g. 10 invocations
    MinSuccessRate  float64 // e.g. 0.9
    MinTrustScore   float64 // e.g. 0.7 (Sanctum)
    MinSharedDays   int     // e.g. 14 days in shared
    MaxArchivedAge  int     // days before auto-archive without use
}

// DefaultPromotionPolicy returns sensible defaults.
func DefaultPromotionPolicy() PromotionPolicy {
    return PromotionPolicy{
        MinUsageCount:  10,
        MinSuccessRate: 0.9,
        MinTrustScore:  0.7,
        MinSharedDays:  14,
        MaxArchivedAge: 90,
    }
}
```

### Algorithm

**Seed (personal stage — zero friction):**

1. Any agent creates a skill in its own scope. No approval, no review.
2. Curator indexes it (summary, tags) for future recall.
3. Stage = Personal.

**Share (grant):**

1. Owner issues a Grant to another agent LU.
2. Sanctum evaluates the grant against trust scoring (owner's trust in
   grantee, or grantee's need).
3. If allowed, skill becomes visible to the grantee. Stage = Shared.

**Promote (validation gates):**

1. Curator's promotion check runs periodically (or on demand):
   - UsageCount ≥ MinUsageCount
   - SuccessRate ≥ MinSuccessRate
   - TrustScore ≥ MinTrustScore (from Sanctum)
   - Time in Shared ≥ MinSharedDays
2. If all gates pass, Curator requests a Seal signature from the owner
   (owner confirms identity).
3. Stage = Promoted — visible to all agents in the org.

**Org pack (versioned distribution):**

1. Promoted skills are collected into git-based skill packs (a pack = a
   repository of SKILL.md files, like QM's git-based skill packs).
2. Packs are versioned; agents pull packs on startup or on refresh.
3. Updates to a pack skill re-enter the pipeline at Shared (not Promoted) —
   regressions are caught before re-promotion.

**Archive (lifecycle):**

1. If a skill has no usage for MaxArchivedAge days, Curator moves it to
   Archived.
2. Archived skills remain searchable (Recall) and can be re-seeded by the
   owner without going through the full pipeline again.

### Integration Points

| Component | Role |
|-----------|------|
| Curator | Skill store, lifecycle, promotion check, archive, recall |
| Sanctum | Trust scoring per agent pair; grant authorization |
| Seal | Signatures: skill identity, owner confirmation, pack signing |
| Gauge | UsageCount, SuccessRate telemetry (promotion gate inputs) |
| Chronicle | Audit: create/grant/promote/archive events |
| Nexus | Skill routing: which agent's skill store to consult for a task |

### QM Adaptation Differences

| QM | MACS |
|----|------|
| Scope owned by *person* | Scope owned by *agent* (AgentContext) |
| Admin-gated promotion (human org hierarchy) | Curator policy gates + Sanctum trust scoring (agent-native) |
| Grants by human admin | Grants by agent owner, authorized by Sanctum |
| Skill packs per org | Skill packs per org, signed by Seal |

The core mechanism (seed cheap, promote by evidence) is identical. The
difference is *who* decides: QM uses human admins; MACS uses policy +
telemetry + trust scores, with human override available at the org level.

## Implementation Plan

**Phase 1 — Skill store + lifecycle (≈300 lines, pure Go, no external deps):**
- `Skill`, `Stage`, `Grant` types
- Store: AddSkill / GetSkill / UpdateStage / Archive
- Stage transition rules (valid transitions only)
- Unit tests: lifecycle transitions, invalid transitions, archive TTL

**Phase 2 — Promotion gate (≈200 lines):**
- PromotionPolicy evaluation against skill stats
- Table-driven tests for gate combinations

**Phase 3 — Integration (needs Sanctum + Seal + Gauge APIs):**
- Grant authorization via Sanctum
- Signature verification via Seal
- Usage telemetry from Gauge
- Git-based org pack export/import

**Non-Goals:**
- No skill *content* validation (we don't judge whether a skill is well-written;
  usage + success rate do that)
- No cross-org skill marketplace (org boundary = pack boundary)
- No automatic promotion (promotion requires explicit owner confirmation +
  signature)

## Risks

| Risk | Mitigation |
|------|-----------|
| Low-quality skills pollute shared stage | Promotion gate requires evidence; sharing is by explicit grant |
| Trust score gaming (agents inflating each other) | Sanctum scoring design; Chronicle audit; human override |
| Skill pack drift (forked packs diverge) | Versioned packs; updates re-enter at Shared stage |
| Zero adoption (nobody seeds skills) | Seed is zero-friction; org can seed starter packs |
