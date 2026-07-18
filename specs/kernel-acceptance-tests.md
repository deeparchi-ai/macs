# MACS Kernel — Acceptance Tests

> **Executor**: Hermes Agent (邝谧)
> **Target**: `deeparchi-ai/macs-kernel-go` @ main
> **Precondition**: repo cloned, `go test ./...` exits 0

---

## AT-1: Build & Lint

| # | Criterion | Expected |
|:--:|-----------|----------|
| 1 | `go build ./...` | exit 0 |
| 2 | `go vet ./...` | exit 0 |
| 3 | `go test ./...` | exit 0 |
| 4 | test count | ≥ 15 PASS |

---

## AT-2: Arbiter — Admission

| # | Criterion | Expected |
|:--:|-----------|----------|
| 5 | green + L1 + importance-2 | Allow |
| 6 | yellow + L1 + importance-2 | Allow + DegradeTo set |
| 7 | red + L3 only + importance-2 | Deny |
| 8 | red + L1 + importance-2 | Allow + DegradeTo set |
| 9 | black + importance-1 + L1 | Allow |
| 10 | black + importance-2 + L1 | Deny |

---

## AT-3: Brake — Circuit Breaker

| # | Criterion | Expected |
|:--:|-----------|----------|
| 11 | Execute succeeds N times → CB stays closed | State = Closed |
| 12 | Execute fails N times (MaxFailures) → CB opens | State = Open |
| 13 | Open → timeout → State = HalfOpen | State = HalfOpen |
| 14 | HalfOpen + success → Closed | State = Closed |
| 15 | HalfOpen + failure → Open | State = Open |
| 16 | TripReason() after open | Non-empty string |

---

## AT-4: Audit — Hook Registry

| # | Criterion | Expected |
|:--:|-----------|----------|
| 17 | Emit event → registered hook called | Hook invoked |
| 18 | Emit event → hook count matches registered hooks | Return value = hooks |
| 19 | Remove hook → emit → hook not called | Not invoked |

---

## AT-5: Trace — W3C traceparent

| # | Criterion | Expected |
|:--:|-----------|----------|
| 20 | NewSpanContext → inject → extract → round-trip | TraceID matches |
| 21 | NewChildSpan → parent TraceID preserved | Same TraceID |
| 22 | NewChildSpan → SpanID different from parent | Different SpanID |
| 23 | ExtractTraceparent malformed header | Error returned |

---

## AT-6: Lock — Concurrency

| # | Criterion | Expected |
|:--:|-----------|----------|
| 24 | AcquireRead → held | Lock held |
| 25 | ReleaseRead → no longer held | Not held |
| 26 | AcquireWrite + AcquireRead (different goroutine) → read blocks | Timeout |
| 27 | AcquireWrite + AcquireWrite (different goroutine) → write blocks | Timeout |
| 28 | AcquireRead + AcquireRead (different goroutine) → both succeed | Both held |
| 29 | AcquireWrite + ReleaseWrite + AcquireRead → read succeeds | Read held |
| 30 | AcquireRead with timeout=0 on locked → error | Error returned |
| 31 | HeldLocks() returns all active locks | Correct list |

---

## Summary

| Category | Checks | Weight |
|----------|:--:|:--:|
| AT-1 Build/Lint | 1-4 | Gate |
| AT-2 Arbiter | 5-10 | Critical |
| AT-3 Brake | 11-16 | Critical |
| AT-4 Audit | 17-19 | Standard |
| AT-5 Trace | 20-23 | Standard |
| AT-6 Lock | 24-31 | Critical |

**Gate**: AT-1 must pass.
**Accept**: 31/31 checks pass.

---

*Acceptance criteria version 1.0 · 2026-07-18*
