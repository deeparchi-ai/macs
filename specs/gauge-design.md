# MACS §9 — Gauge: Performance Metrics & Cross-Vendor Health

> **DeepArchi · 邝谧**
> *Working Draft v0.1 — Pre-implementation design for the performance metrics subsystem.*
> IBM lineage: **RMF** (Resource Measurement Facility) + **NetView** (network monitoring)

## Abstract

Gauge is the MACS telemetry subsystem that collects, aggregates, and correlates agent performance metrics — latency, token consumption, vendor API health, and link quality. It detects cross-vendor degradation patterns that indicate external infrastructure problems rather than single-provider outages.

## Problem

Multi-agent systems call multiple LLM providers concurrently. A spike in `p95` latency from a single provider looks like a vendor outage; a simultaneous spike across all three providers indicates a network or infrastructure problem. Without **cross-vendor correlation**, each provider degradation is treated as an isolated incident, wasting operator attention and delaying root-cause analysis.

Existing monitoring tools (Prometheus, Datadog) are push-based and designed for service-level metrics, not agent-level decision quality. They lack the concept of a "vendor health" metric that combines API success rate, token throughput, and response latency into a single signal. Gauge fills this gap by collecting metrics at agent granularity, aggregating them into summary statistics (p50/p95/p99), and emitting correlated health signals that Warden §12 can act on.

The subsystem also tracks **link quality** and **success rate** — distinct from raw latency. An agent may respond quickly (low latency) but fail 40% of the time (low success rate). Gauge treats these as independent axes so that Warden's recovery policies can distinguish "slow but working" from "fast but broken."

## Mainframe Analogy

IBM z/OS **RMF (Resource Measurement Facility)** collects and reports system-wide performance data — CPU utilization, I/O rates, storage throughput — and feeds it to WLM for automatic resource adjustment. **NetView** monitors the network for link failures and performance degradation. Gauge combines both roles: RMF-style metric collection with NetView-style link-quality monitoring, outputting structured data that Warden (the MACS equivalent of System Automation) consumes for automated recovery decisions.

## Data Model

```go
// MetricType classifies what is being measured.
type MetricType int

const (
    MetricLatencyP50  MetricType = iota // response time median
    MetricLatencyP95                    // response time 95th percentile
    MetricLatencyP99                    // response time 99th percentile
    MetricTokenRate                     // tokens consumed per second
    MetricVendorHealth                  // API success rate 0-1
    MetricSuccessRate                   // task completion rate 0-1
    MetricLinkQuality                   // network link health 0-1
)

// Metric is a single measurement data point.
type Metric struct {
    Name      string
    Type      MetricType
    Value     float64
    Timestamp time.Time
    Tags      map[string]string
    Source    string // agent or subsystem name
}

// MetricSummary holds aggregate statistics of a metric series.
type MetricSummary struct {
    Count  int
    Avg    float64
    Min    float64
    Max    float64
    P50    float64
    P95    float64
    P99    float64
}

// MetricRegistry collects, queries, and aggregates metric data points.
type MetricRegistry struct {
    mu      sync.RWMutex
    metrics []Metric
}
```

**Key methods:**
- `Add(m Metric)` — record a data point
- `Query(mt MetricType, window time.Duration) []Metric` — filter by type + time window
- `QueryBySource(source string, window time.Duration) []Metric` — filter by agent
- `Aggregate(mt MetricType, window time.Duration) MetricSummary` — compute p50/p95/p99

## Algorithm

### 1. Metric Ingestion
```
Agent → Gauge.Add(Metric{Type: MetricLatencyP95, Value: 320ms, Source: "xval-opus", ...})
     → stored in registry with timestamp and tags
```

### 2. Cross-Vendor Correlation
```
Step 1: Query MetricVendorHealth for each vendor over last 5 minutes
Step 2: If all 3 vendors drop below 0.8 → emit "external-degradation" event
Step 3: If only 1 vendor drops → emit "vendor-degraded:<vendor>" event
Step 4: If latency rises without health drop → emit "vendor-slow:<vendor>"
```

### 3. Aggregate Computation
```
Summarize(metrics []Metric) MetricSummary:
  1. If empty, return MetricSummary{Count: 0}
  2. Extract values into float64 slice
  3. Compute min, max, sum in single pass
  4. Sort values
  5. Compute p50, p95, p99 via linear interpolation
  6. Return MetricSummary
```

### 4. Health Scoring (future phase)
```
Score(agent string, window time.Duration) float64:
  latencyScore  = 1.0 - normalize(latency, threshold)
  successScore  = successRate
  healthScore   = successRate
  return weighted average, clamped to [0, 1]
```

## Integration Points

| Consumed by Gauge | Purpose |
|------|------|
| Agents (via XVal §5, Cadence §6) | Emit latency/token/success metrics |
| Relay §11 | Receive cluster-wide health events |

| Consumed from Gauge | By | Purpose |
|------|------|------|
| `MetricRegistry.Aggregate()` | Warden §12 | Feed into recovery policies (`gauge.latency.p95 > 5000`) |
| `MetricRegistry.Query()` | Chronicle §4 | Audit trail of performance data |
| Cross-vendor correlation events | Warden §12 | Trigger vendor-degraded escalations |
| Health scoring output | Pulse §13 | Contribute to self-health aggregate |

## Implementation Plan

| Phase | Lines | Scope |
|------|:-----:|------|
| Phase 1 | ~150 | Metric struct, MetricType enum, MetricRegistry (Add/Query/QueryBySource) |
| Phase 2 | ~80 | Summarize, MetricSummary, Aggregate, percentile computation |
| Phase 3 | ~100 | Cross-vendor correlation detector, event emission |
| Phase 4 | ~70 | Health scoring algorithm, integration with Warden condition DSL |
| **Total** | **~400** | |

## Non-Goals

- **Push-based remote collection** — Gauge is an in-process registry; remote collection is Chronicle's concern.
- **Time-series database** — Gauge stores metrics in memory; persistence is delegated to Chronicle §4.
- **Alerting rules** — Gauge emits structured events; Warden §12 owns the alerting/rules engine.
- **Distributed tracing** — Span-level trace collection is outside scope; Gauge handles aggregate metric points only.
- **Model quality metrics** — "Was the answer good?" is a subjective evaluation (XVal §5 territory), not a metric.
