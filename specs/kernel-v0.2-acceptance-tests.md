# MACS Kernel v0.2 — Acceptance Tests

> **Executor**: Hermes Agent (邝谧)
> **Target**: `deeparchi-ai/macs-kernel-go` @ main, v0.2
> **Precondition**: `go test ./...` exits 0, ≥48 tests (31 v0.1 + 17 v0.2)

---

## AT-1: Build & Lint

| # | Criterion | Expected |
|:--:|-----------|----------|
| 1 | `go build ./...` | exit 0 |
| 2 | `go vet ./...` | exit 0 |
| 3 | `go test ./...` | exit 0 |
| 4 | Test count | ≥48 PASS |

---

## AT-2: PARMLIB

| # | Criterion | Test |
|:--:|-----------|------|
| 5 | `parmlib.Load("IEASYS", &cfg)` → kernel.max_agents = 256 | `TestPARMLIB_Load_IEASYS` |
| 6 | `parmlib.Load("NONEXIST", &cfg)` → error | `TestPARMLIB_Load_NotFound` |
| 7 | Load malformed YAML file → error | `TestPARMLIB_Load_BadYAML` |
| 8 | `parmlib.List()` → returns all member names, no .yaml suffix | `TestPARMLIB_List` |
| 9 | PARMLIB directory contains 15 files | manual check: `ls etc/macs-parmlib/*.yaml \| wc -l` = 15 |

---

## AT-3: Registry (CSA)

| # | Criterion | Test |
|:--:|-----------|------|
| 10 | `GetAgent("nonexistent")` → nil | `TestRegistry_GetAgent_NotFound` |
| 11 | First `UpdateAgent` creates entry | `TestRegistry_UpdateAgent_Creates` |
| 12 | `UpdateAgent` modifies in-place via closure | `TestRegistry_UpdateAgent_Modifies` |
| 13 | `ListAgents(filter)` returns only matching agents | `TestRegistry_ListAgents_Filter` |
| 14 | 100 goroutines, concurrent updates, no panic | `TestRegistry_Concurrent` |
| 15 | `RegisterCB` + `GetCB` round-trip | test |
| 16 | `RegisterJob` + `GetJob` + `ListJobs` round-trip | test |

---

## AT-4: Dispatch Table (SVC)

| # | Criterion | Test |
|:--:|-----------|------|
| 17 | Admit function registered and callable via dispatch table | `TestDispatchTable` |
| 18 | Status function registered and callable | test |

---

## AT-5: Subpool (GETMAIN)

| # | Criterion | Test |
|:--:|-----------|------|
| 19 | `Create("agent-a")` → subpool created | `TestSubpool_Create` |
| 20 | `AddKey` three times → `Release` returns three keys | `TestSubpool_Release_FreesKeys` |
| 21 | `Release` removes pool, `Get` returns nil | `TestSubpool_Release_RemovesPool` |
| 22 | `Count()` reflects active subpools | test |

---

## AT-6: Checkpoint (JES2 Checkpoint)

| # | Criterion | Test |
|:--:|-----------|------|
| 23 | Two goroutines `Claim` same job → exactly one returns true | `TestCheckpoint_Claim_Atomic` |
| 24 | `Release` → job becomes claimable again | `TestCheckpoint_Release` |
| 25 | `Register` + `Get` round-trip | `TestCheckpoint_Register_Get` |
| 26 | `List("running")` returns only running jobs | `TestCheckpoint_List_Filter` |

---

## AT-7: Backward Compatibility

| # | Criterion | Expected |
|:--:|-----------|----------|
| 27 | v0.1 tests still pass (Arbiter/Brake/Audit/Trace/Lock) | 31/31 |
| 28 | `go.mod` still `go 1.21` | no version bump |

---

## AT-8: PARMLIB Members (Manual)

| # | Criterion | Expected |
|:--:|-----------|----------|
| 29 | `etc/macs-parmlib/IEASYS.yaml` exists and is valid | YAML parseable |
| 30 | 14 subsystem members exist (REGULAT through CONSOLxx) | All .yaml files present |
| 31 | Each member file is valid YAML | YAML parseable |
| 32 | No member name exceeds 8 characters | `ls \| grep -E '[a-zA-Z]{9,}'` = empty |

---

## Summary

| Category | Checks | Weight |
|----------|:--:|:--:|
| AT-1 Build/Lint | 1-4 | Gate |
| AT-2 PARMLIB | 5-9 | Critical |
| AT-3 Registry | 10-16 | Critical |
| AT-4 Dispatch | 17-18 | Standard |
| AT-5 Subpool | 19-22 | Standard |
| AT-6 Checkpoint | 23-26 | Critical |
| AT-7 Backward Compat | 27-28 | Gate |
| AT-8 PARMLIB Members | 29-32 | Standard |

**Gate**: AT-1 + AT-7 must pass.
**Accept**: 32/32 checks pass.
