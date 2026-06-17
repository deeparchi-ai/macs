# Upstreaming macs_dump → NousResearch/hermes-agent

Hermes has **no GitHub Discussions**. Path: comment on **#6741** (structured
tracing — open, unclaimed, design not dictated) to propose + claim, then open a
small **Draft PR** referencing it. The working, on-box-verified plugin is the
strongest design signal. Skip a separate proposal issue (redundant with #6741).

---

## Draft PR

**Title**
```
feat(plugins): add macs_dump — conditional decision-chain dump (observability)
```

**Body**

> ### What
> A self-contained `observability/macs_dump` plugin that captures the **full
> decision chain of a turn** as a JSON artifact **when a trigger fires** —
> a tool fails N times, latency exceeds a budget, or the model finishes
> abnormally. The artifact (`macs.dump.v0`) bundles: system prompt + input
> messages, the full LLM response, the tool-call sequence with results, timings
> and token/cost — keyed by `(session_id, task_id)`.
>
> Think of it as `strace`/core-dump for an agent turn: logs tell you *what
> happened*; a dump preserves *what the world looked like at the instant it did*.
>
> ### Why
> Today, when an agent quietly goes wrong (tool keeps timing out, response gets
> truncated), the evidence is scattered across the transcript and gone by the
> time anyone looks. This gives a single, self-contained snapshot to debug from —
> complementary to **#6741** (it reuses the same correlation IDs #6741 wants and
> can populate/consume that trace layer) and a concrete slice of **#6642**.
>
> ### How — minimal and safe
> - **Read-only observer hooks** only (`pre/post_api_request`, `pre/post_tool_call`,
>   `on_session_finalize`). **No middleware. Zero core changes.**
> - **fail-open**: every hook body is wrapped; a bug here can never break a turn.
> - **Self-contained**: standard library only, **zero new dependencies**.
> - **Quiet by default**: SLIP-style escalation triggers (repeat-fail / latency /
>   abnormal-finish) — no dump on transient hiccups. Bounded per-turn ring
>   buffer, evicted on `on_session_finalize`.
> - Output: `~/.hermes/macs-dump/<date>/` + `index.jsonl`. Opt-in via
>   `hermes plugins enable observability/macs_dump`.
>
> ### Testing
> - Unit tests for triggers, collector, and the adapter.
> - **Verified on Hermes v0.16.0**: registered into the real `PluginManager` and
>   driven through the real `invoke_hook` dispatcher; produces a valid artifact
>   (sample below). Tested on `pre_api_request` payload shapes
>   (`request_messages`), result-encoded tool errors, `api_duration` seconds,
>   and `on_session_finalize` eviction.
>
> ### Scope
> One new plugin folder under `plugins/observability/`. Nothing else touched.
> Sample artifact and the runtime-agnostic spec/schema: <macs repo link>.
>
> Relates to #6741, #6642.

---

## Comment to post on #6741

> Working on a complementary angle here and would love a maintainer steer before
> I open a PR.
>
> #6741 is about the **trace/span timeline**; the gap I keep hitting in practice
> is **post-hoc evidence** — when an agent quietly misbehaves (a tool times out
> repeatedly, a response gets truncated), by the time I look the context is gone.
>
> I've built a small read-only `observability/macs_dump` plugin that, **when a
> SLIP-style condition fires** (tool fails N times / latency over budget /
> abnormal finish), freezes the **whole decision chain of that turn** — system
> prompt + input, full LLM response, tool-call sequence + results, timings/tokens
> — into one self-contained JSON artifact keyed by `(session_id, task_id)`. It
> reuses the same correlation IDs #6741 wants, so the two compose: #6741 gives the
> timeline, this gives the frozen snapshot at the failure instant.
>
> Properties: **observer hooks only, no middleware, zero core changes, fail-open,
> stdlib-only, quiet by default**. Verified against v0.16.0 (registers into the
> real PluginManager, fires through the real `invoke_hook`). Sample artifact:
> <link>.
>
> Happy to (a) claim the tracing/timestamp work in #6741 as part of this, and
> (b) open it as a small Draft PR so you can review the diff. Does a standalone
> `observability/` plugin sound like the right shape, or would you rather this
> land inside the core session schema?

---

## Mergeability checklist
- [ ] Conventional Commit title (`feat(plugins): …`)
- [ ] One logical change, plugin folder only
- [ ] `scripts/run_tests.sh` green; manual test steps in PR body
- [ ] Screenshots/sample artifact attached
- [ ] References #6741 (and #6642)
- [ ] License headers OK (MIT, matches repo)
