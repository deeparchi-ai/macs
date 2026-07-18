# MACS §14 Console — Acceptance Tests

> **Executor**: Hermes Agent (邝谧)
> **Target**: `deeparchi-ai/macs-console-go` @ main
> **Precondition**: repo cloned, `go test ./...` exits 0

---

## AT-1: Build & Lint

```
Check: go build ./... exits 0
Check: go vet ./... exits 0
Check: go test ./... exits 0
Check: go test ./... -count=1 -v shows ≥ 20 PASS lines
```

| # | Criterion | Expected | Actual |
|:--:|-----------|----------|:------:|
| 1 | `go build ./...` | exit 0 | |
| 2 | `go vet ./...` | exit 0 | |
| 3 | `go test ./...` | exit 0 | |
| 4 | test count | ≥ 20 PASS | |

---

## AT-2: Top-Level Help

```
$ macs-console --help
$ macs-console help
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 5 | `--help` flag | Prints command list with all 8 nouns |
| 6 | `help` command | Same output as --help |
| 7 | Unknown command | Prints error + help, exit ≠ 0 |

---

## AT-3: Status Command

```
$ macs-console status
$ macs-console status --output json
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 8 | `status` default | Table with all 14 subsystems (including Console) |
| 9 | `status --output json` | Valid JSON, `"subsystems"` array, 14 entries |
| 10 | JSON parseable | `jq .status` returns string |

---

## AT-4: Agent Lifecycle

```
$ macs-console agent list
$ macs-console agent list --output json
$ macs-console agent start research.prod
$ macs-console agent stop research.prod
$ macs-console agent restart research.prod
$ macs-console agent start          # ← missing arg
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 11 | `agent list` | Table with ≥ 1 agent |
| 12 | `agent list --output json` | Valid JSON array of agents |
| 13 | `agent start <lu>` | Confirmation message with "started" + fork-point timestamp |
| 14 | `agent stop <lu>` | Confirmation message with "stopped" |
| 15 | `agent restart <lu>` | Confirmation message with "restarted" |
| 16 | `agent start` (no args) | Error message, exit ≠ 0 |

---

## AT-5: Job Queue

```
$ macs-console job list
$ macs-console job list --status=done
$ macs-console job list --output json
$ macs-console job output <job-id>
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 17 | `job list` | Table with ≥ 2 jobs |
| 18 | `job list --status=done` | Only "done" status jobs shown |
| 19 | `job output <id>` | Non-empty output text for valid job id |

---

## AT-6: Audit Query

```
$ macs-console audit query
$ macs-console audit query --agent=researcher
$ macs-console audit query --since=2026-07-01T00:00:00Z
$ macs-console audit query --trace=abc123
$ macs-console audit query --output json
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 20 | `audit query` (no filters) | Table with ≥ 3 entries |
| 21 | `--agent` filter | Only entries for that agent |
| 22 | `--trace` filter | Only entries with matching trace ID |
| 23 | `--output json` | Valid JSON array of audit entries |

---

## AT-7: Metrics

```
$ macs-console metric show
$ macs-console metric show --subsystem=XVal
$ macs-console metric show --window=5m
$ macs-console metric show --output json
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 24 | `metric show` default | Multi-metric output |
| 25 | `--subsystem` filter | Only metrics for that subsystem |
| 26 | `--output json` | Valid JSON |

---

## AT-8: Identity Management

```
$ macs-console identity list
$ macs-console identity list --status=active
$ macs-console identity register --lu=test.prod --card=https://a.com/card --key=abc123
$ macs-console identity rotate --lu=test.prod --new-key=xyz789
$ macs-console identity revoke --lu=test.prod --reason="test done"
$ macs-console identity list --status=revoked   # ← should show test.prod
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 27 | `identity list` | Table with ≥ 1 identity |
| 28 | `identity register` | Confirmation + status "active" |
| 29 | `identity rotate` | Confirmation + "rotation started" |
| 30 | `identity revoke` | Confirmation + "revoked" |
| 31 | `identity list --status=revoked` | Shows revoked identity |
| 32 | Chain: register → rotate → revoke | All three steps succeed in sequence |

---

## AT-9: Policy Management

```
$ macs-console policy list
$ macs-console policy edit --name=crash-loop --action=append escalate_after=15m
$ macs-console policy activate --name=crash-loop
$ macs-console policy edit --name=nonexistent --action=append x=y   # ← should error
```

| # | Criterion | Expected |
|:--:|-----------|----------|
| 33 | `policy list` | Table with ≥ 2 policies |
| 34 | `policy edit` valid | Confirmation + "updated" |
| 35 | `policy activate` | Confirmation + "activated" |
| 36 | `policy edit` nonexistent | Error message, exit ≠ 0 |

---

## AT-10: JSON Output Consistency

Run every command with `--output json` and verify:

| # | Criterion | Expected |
|:--:|-----------|----------|
| 37 | All 12 commands with `--output json` | Valid JSON, parseable by `jq` |
| 38 | Error cases with `--output json` | JSON with `"error": "..."` field |

---

## Summary

| Category | Checks | Weight |
|----------|:--:|:--:|
| AT-1 Build/Lint | 1-4 | Gate |
| AT-2 Help | 5-7 | Gate |
| AT-3 Status | 8-10 | Critical |
| AT-4 Agent | 11-16 | Critical |
| AT-5 Job | 17-19 | Standard |
| AT-6 Audit | 20-23 | Standard |
| AT-7 Metrics | 24-26 | Standard |
| AT-8 Identity | 27-32 | Critical |
| AT-9 Policy | 33-36 | Standard |
| AT-10 JSON | 37-38 | Critical |

**Gate**: AT-1, AT-2 must pass before proceeding.
**Accept**: AT-1 through AT-9 all pass (36/36 checks).
**JSON bonus**: AT-10 (38/38 total).

---

*Acceptance criteria version 1.0 · 2026-07-18*
