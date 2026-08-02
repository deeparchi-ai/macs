# Contributing to MACS

MACS is a spec-first project. Fourteen subsystems, each with a design spec before a line of Go.
We welcome contributions — but the entry point is **design**, not code.

## The Short Version

> Write a design proposal. We'll burn our tokens on implementation.

This is modelled on [QM's contribution model](https://github.com/yc-software/qm/blob/main/CONTRIBUTING.md):
human-written text, casual and direct, submitted as a markdown file.

## How to Contribute

### 1. Design Proposal (ADR)

Submit a PR that adds a `.md` file to `specs/decisions/`. Describe:

- **What** you want to change or add
- **Why** — the problem it solves
- **How** — enough design detail that a maintainer can implement it
- **Impact** — which subsystems are affected, any breaking changes

Keep it informal. A few paragraphs is fine. Do not have AI expand your idea into a
formal document — we want your reasoning, not your token budget.

### 2. Alignment

A maintainer will review. If we're aligned, we'll implement it and credit you.
If we see the problem differently, we'll explain why — and you learn the design
constraints we're working within.

### 3. What We Accept as Code PRs

| Type | Accepted? | Notes |
|------|-----------|-------|
| Design proposal (ADR) | ✅ Yes | Preferred path |
| Bug report + fix | ✅ Yes | Small, focused PRs |
| Test additions | ✅ Yes | Especially edge cases |
| Doc fixes | ✅ Yes | Typos, clarifications, missing context |
| New subsystem implementation | ❌ No | Must be preceded by an accepted ADR |
| Large refactors | ❌ No | Must be preceded by an accepted ADR |

### 4. Security Issues

Report vulnerabilities privately. See [SECURITY.md](https://github.com/deeparchi-ai/macs/blob/main/SECURITY.md).
Do not open a public issue or PR.

## Why This Model?

- **MACS has a unified architecture model.** The 14 subsystems are tightly coupled
  through z/OS design patterns (CICS regions, WLM goal scheduling, RACF access
  control). Ad-hoc code contributions risk breaking design coherence.
- **Specs are the interface.** You don't need to learn 14 Go packages to contribute.
  You need to understand the problem space and propose a solution.
- **Implementation is the easy part.** With a clear spec, our agents can produce
  well-typed, tested Go code. The hard part is knowing *what* to build.

## Prior Art

- [QM CONTRIBUTING.md](https://github.com/yc-software/qm/blob/main/CONTRIBUTING.md) —
  the original inspiration for human-written design proposals
- [MACS Governance Specification v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md) —
  the canonical spec for all 14 subsystems
- [macs/specs/](specs/) — per-subsystem design specs and acceptance tests
- [specs/decisions/ADR-001-contribution-model.md](specs/decisions/ADR-001-contribution-model.md) —
  the ADR that established this policy

## License

By contributing, you agree that your contributions will be licensed under the
MIT License. See [LICENSE](LICENSE).
