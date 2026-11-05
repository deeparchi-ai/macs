# Changelog

All notable changes to MACS are documented here.
Format: date · change · reason. Positioning changes are recorded even when no code changes.

## Unreleased

### 2026-11-05 — Positioning change

- **Changed positioning:** from *"MACS is the Agent OS"* to *"the cross-runtime artifact
  admission and evidence layer"*. Input: a plugin/skill package plus a policy. Output:
  allow/deny, the rationale, and a regulator-ready evidence package.
- **Explicit non-goals now stated:** MACS does not take over runtimes, hold sessions, or
  touch tokens (`SPEC.md`, Non-Goals).
- **Why:** hosted agent platforms (Kimi Hosted Agents, and equivalents) now ship sandboxing,
  network policy, tool permissions, audit export and metering as platform primitives
  — permissive by default (`networking: unrestricted`, `permission_policy: always_allow`).
  Runtime governance is therefore no longer a defensible product boundary; artifact
  admission and externally presentable evidence are.
- **Unchanged:** the fourteen subsystems, their code, tests, and numbering (§2–§14). In the
  new positioning they are the implementation of the admission and evidence layers, not a
  runtime kernel.
