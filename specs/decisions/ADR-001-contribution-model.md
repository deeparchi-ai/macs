# ADR-001: Design-First Contribution Model

**Status:** Accepted  
**Date:** 2026-08-03  
**Author:** 邝谧 (kuangmi@deeparchi.com.cn)  
**Inspired by:** [QM CONTRIBUTING.md](https://github.com/yc-software/qm/blob/main/CONTRIBUTING.md)

## Context

MACS has 14 subsystems, each with a design spec, Go implementation, and POC
integration tests. The codebase is spec-first: every subsystem traces back to a
design decision documented in `specs/` or the MACS Governance Specification.

As we open MACS to external contributors, we face a choice:

- **Open code PRs** — accept any Go contribution that passes tests
- **Design-first PRs** — require a design proposal before code

QM (yc-software/qm) chose the latter with an explicit rule: "Submit PRs as
human-written text in `adrs/`. We'll burn our tokens on implementation."

## Decision

**MACS adopts a design-first contribution model.** External contributors submit
design proposals (ADRs) rather than code. Implementation is done by MACS
maintainers after design alignment.

### What this means

1. New subsystems, major refactors, and API changes require an ADR in
   `specs/decisions/` before implementation
2. Bug fixes, test additions, and doc fixes are exempt — small, focused code
   PRs are welcome for these
3. ADRs should be human-written, informal, and concise — no AI-expanded
   formal documents
4. Once an ADR is accepted, the contributor is credited in the implementation
   commit

### Why not accept arbitrary code PRs?

- **Design coherence risk.** MACS's 14 subsystems follow z/OS design patterns
  (CICS task isolation, WLM goal scheduling, RACF access control). Ad-hoc code
  contributions risk breaking the unified architecture.
- **Spec is the interface.** An external contributor shouldn't need to
  understand 14 Go packages to propose a change. They need to understand the
  problem space.
- **Implementation efficiency.** With a clear spec, the MACS team's agents
  produce well-typed, tested Go code efficiently. Removing the spec bottleneck
  is the contribution model's goal.

## Consequences

### Positive

- Lower barrier to entry: contributors write markdown, not Go
- Design decisions are documented and searchable (the `specs/decisions/`
  directory becomes a knowledge base)
- MACS architecture stays coherent — every change traces to a reasoned decision
- Aligns with MACS's existing spec-first workflow

### Negative

- Slower turnaround for external contributors who want to write code directly
- Creates a bottleneck on maintainer implementation bandwidth
- May deter contributors who prefer to submit self-contained PRs

### Mitigations

- Bug fixes, tests, and doc fixes are exempt — fast path for small
  contributions
- ADR review is lightweight: alignment, not exhaustive design review
- As the team grows, we can delegate implementation to trusted contributors

## Alternatives Considered

### A. Open Code PRs (rejected)

Standard open-source model. Rejected because MACS's architecture is too
tightly coupled for ad-hoc code contributions to maintain coherence.

### B. CLA + code review (rejected)

Requiring a CLA and detailed code review would add process without solving
the design coherence problem. A well-reviewed PR can still break architecture
if the design wasn't discussed first.

### C. Spec PRs only, no code at all (rejected)

Too restrictive. Bug fixes and test additions should be welcome as code PRs
without going through the full ADR process.

## References

- [QM CONTRIBUTING.md](https://github.com/yc-software/qm/blob/main/CONTRIBUTING.md)
- [MACS Governance Specification v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)
- [QM Architecture](https://github.com/yc-software/qm#architecture) — per-scope sandbox model
