# ADR-002: Framework ↔ Implementation Decoupling

**Status:** Accepted  
**Date:** 2026-10-24  
**Author:** sg-architect (DEEPAR-000) — confirmed by 邝谧  
**Supersedes:** ADR set on the orphan `master` branch (2026-07-18), never merged into `main`

## Context

MAEA is a framework: it absorbs external architecture results without restriction
(IBM z/OS subsystem family, TOGAF, AI-native org research, Google A2A / Anthropic MCP,
and future candidates such as Palantir Ontology or IT4IT).

MACS is an implementation. If every absorption automatically became MACS work, the
roadmap would be driven by reading lists instead of user needs. If, conversely, MACS
ignored the framework, the framework would drift into a pile of unread theory.

We need a rule that keeps the framework free to absorb and the implementation free to
stay small — while making every "not now" decision traceable.

Decision owner's framing: *"MAEA 是框架，理论上他们的架构成果都可以吸收；MACS 实现是否采用
进行评估，或者未来规划不同版本进行适配。"*

## Decision

Three layers, one direction of flow:

```
External architecture result
   │
   ▼  ① ABSORB — MAEA side, unrestricted
MAEA-Framework/docs/adoptions/A-NNN-*.md   (adoption register)
   │      + specs/ or docs/ body text
   ▼  ② EVALUATE — each absorbed item gets exactly one MACS verdict
this directory: specs/decisions/ADR-NNN-*.md
   │
   ▼  ③ ROUTE — verdict must be one of three
adopted   → implementation (subsystem spec + Go repo + POC test)
deferred  → version-mapped (vX.Y named in this ADR; no silent backlog)
rejected  → reason recorded in the ADR (never silently dropped)
```

Rules:

1. **Absorption ≠ adoption.** Nothing in `docs/adoptions/` obliges MACS to implement it.
2. **No orphan absorptions.** Every `A-NNN` entry must reference a MACS verdict —
   adopted, deferred with a version, or rejected with a reason.
3. **Deferral is versioned, not vague.** "Not now" must name the version that would
   carry it; an unnamed deferral is a rejection and must say so.
4. **Re-evaluation is allowed, silently reversing is not.** A verdict may be revisited,
   but the ADR is amended rather than quietly overwritten.
5. **The governance spec wins.** Where an ADR and
   [`macs-governance-spec.md`](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)
   disagree, the spec is authoritative and the ADR is stale until fixed.

## Current verdicts

| Adoption | Source | MACS verdict | Where |
|:--:|------|------|------|
| A-001 | IBM z/OS subsystem family | **Adopted** — 14 subsystems, v0.1–v0.2 | [`SPEC.md`](../SPEC.md), `macs-*-go` repos |
| A-002 | TOGAF 10 / ADM | **Adopted as mapping only** — no code obligation | governance spec §1 |
| A-003 | AI-native org research | **Adopted** — informs topology, no subsystem | MAEA whitepaper |
| A-004 | Google A2A / Anthropic MCP | **Adopted** — Nexus §8 (VTAM lineage) | `macs-nexus-go` |
| — | A2A conformance (official TCK) | **Deferred, unversioned → treated as open risk** | no version committed |
| — | Palantir Ontology isolation | **Candidate, not absorbed** | none |

## Consequences

- **Positive:** the framework can absorb aggressively without inflating scope; every
  scope omission has a written reason; version planning becomes reviewable.
- **Negative:** each new absorption costs one short ADR — the discipline fails if ADRs
  are skipped, and a skipped ADR is indistinguishable from an unnoticed one.
- **Risk:** ADR drift versus the governance spec (rule 5 exists because this already
  happened once: the read-only-dashboard ADRs on `master` were invalidated by SPEC v3.0,
  which gives MACS enforcement powers — Regulator rate-limits, Warden recovers).

## Notes

- The orphan `master` branch still carries an unrelated 2026-07 history (dashboard-era
  README/DESIGN and six superseded ADRs). It shares no ancestor with `main`. Cleanup is
  a separate decision; until then `main` is the only authoritative branch.
- Adoption register (framework side):
  [`MAEA-Framework/docs/adoptions/`](https://github.com/deeparchi-ai/MAEA-Framework/tree/main/docs/adoptions)
