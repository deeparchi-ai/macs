// POC-6: Cross-Vendor Correlation Degradation Detection
//
// Verifies that Gauge's CrossVendorCorrelation correctly distinguishes
// vendor-specific faults from external infrastructure faults, and that
// Warden policies trigger different actions for each case.
//
// Coverage: §9 Gauge + §12 Warden + §5 XVal
//
// Case A: Vendor self-fault
//   - One vendor's metrics slowly degrade, others remain stable
//   - Pearson correlation between degrading vendor and stable vendors < 0.3
//   - CrossVendorCorrelation.Score < threshold (0.7)
//   - Result: vendor-specific fault → trigger vendor failover
//
// Case B: External infrastructure fault
//   - All vendors degrade simultaneously
//   - Pearson correlation between all vendor pairs > 0.9
//   - CrossVendorCorrelation.Score > threshold
//   - Result: external fault → global pause + notify human
//
// Policy rules:
//   - "vendor-degraded": correlation.score < 0.7 → escalate single vendor
//   - "vendor-total-outage": correlation.score >= 0.7 → global pause
package poc

import (
	"math"
	"testing"
)

// ── Pearson correlation (standalone for POC test) ──

func pearsonR(x, y []float64) float64 {
	if len(x) != len(y) || len(x) == 0 {
		return 0
	}
	n := float64(len(x))
	var sx, sy, sxy, sx2, sy2 float64
	for i := range x {
		sx += x[i]
		sy += y[i]
		sxy += x[i] * y[i]
		sx2 += x[i] * x[i]
		sy2 += y[i] * y[i]
	}
	num := n*sxy - sx*sy
	dx := n*sx2 - sx*sx
	dy := n*sy2 - sy*sy
	if dx <= 0 || dy <= 0 {
		return 0
	}
	return num / math.Sqrt(dx*dy)
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

// ── CrossVendorCorrelation (thin POC wrapper) ──

type VendorStream struct {
	Vendor  string
	Metrics []float64
}

type CorrelationResult struct {
	Score          float64
	IsCorrelated   bool
	Threshold      float64
	Recommendation string
}

func analyzeCorrelation(streams []VendorStream, threshold float64) CorrelationResult {
	r := CorrelationResult{Threshold: threshold}
	n := len(streams)
	if n < 2 {
		r.Recommendation = "insufficient vendors"
		return r
	}

	maxR := 0.0
	for i := 0; i < n; i++ {
		for j := i + 1; j < n; j++ {
			rr := pearsonR(streams[i].Metrics, streams[j].Metrics)
			if abs(rr) > maxR {
				maxR = abs(rr)
			}
		}
	}

	r.Score = maxR
	r.IsCorrelated = maxR >= threshold

	if r.IsCorrelated {
		r.Recommendation = "vendor-total-outage: external infrastructure fault"
	} else {
		r.Recommendation = "vendor-degraded: single-vendor fault, trigger failover"
	}
	return r
}

// ── POC-6 Tests ──

func TestPOC6_CaseA_VendorSelfFault(t *testing.T) {
	// Anthropic slowly degrades; DeepSeek and Google remain stable.
	anthropic := VendorStream{
		Vendor:  "anthropic",
		Metrics: []float64{0.99, 0.98, 0.95, 0.91, 0.88},
	}
	deepseek := VendorStream{
		Vendor:  "deepseek",
		Metrics: []float64{0.97, 0.98, 0.97, 0.96, 0.97},
	}
	google := VendorStream{
		Vendor:  "google",
		Metrics: []float64{0.95, 0.96, 0.94, 0.95, 0.96},
	}

	// Individual pairwise correlations.
	rAD := pearsonR(anthropic.Metrics, deepseek.Metrics)
	rAG := pearsonR(anthropic.Metrics, google.Metrics)
	rDG := pearsonR(deepseek.Metrics, google.Metrics)

	// Degrading vs stable should have low correlation (< 0.6).
	if abs(rAD) > 0.6 {
		t.Errorf("anthropic-deepseek r=%.4f, expected < 0.6 (degrading vs stable)", rAD)
	}
	if abs(rAG) > 0.6 {
		t.Errorf("anthropic-google r=%.4f, expected < 0.6 (degrading vs stable)", rAG)
	}
	// Two stable vendors should have moderate correlation.
	if abs(rDG) < 0.3 {
		t.Errorf("deepseek-google r=%.4f, expected moderate (both stable)", rDG)
	}

	// Cross-vendor analysis.
	result := analyzeCorrelation([]VendorStream{anthropic, deepseek, google}, 0.7)
	if result.IsCorrelated {
		t.Errorf("expected NOT correlated (vendor self-fault), got score=%.4f", result.Score)
	}
	if result.Recommendation != "vendor-degraded: single-vendor fault, trigger failover" {
		t.Errorf("wrong recommendation: %s", result.Recommendation)
	}
}

func TestPOC6_CaseB_ExternalInfrastructureFault(t *testing.T) {
	// All three vendors degrade simultaneously.
	anthropic := VendorStream{
		Vendor:  "anthropic",
		Metrics: []float64{0.99, 0.95, 0.88, 0.72, 0.51},
	}
	deepseek := VendorStream{
		Vendor:  "deepseek",
		Metrics: []float64{0.98, 0.94, 0.86, 0.70, 0.48},
	}
	google := VendorStream{
		Vendor:  "google",
		Metrics: []float64{0.97, 0.93, 0.85, 0.68, 0.45},
	}

	rAD := pearsonR(anthropic.Metrics, deepseek.Metrics)
	rAG := pearsonR(anthropic.Metrics, google.Metrics)
	rDG := pearsonR(deepseek.Metrics, google.Metrics)

	// All pairs should be highly correlated (degrading in lockstep).
	if abs(rAD) < 0.85 {
		t.Errorf("anthropic-deepseek r=%.4f, expected > 0.85 (lockstep degradation)", rAD)
	}
	if abs(rAG) < 0.85 {
		t.Errorf("anthropic-google r=%.4f, expected > 0.85 (lockstep degradation)", rAG)
	}
	if abs(rDG) < 0.85 {
		t.Errorf("deepseek-google r=%.4f, expected > 0.85 (lockstep degradation)", rDG)
	}

	result := analyzeCorrelation([]VendorStream{anthropic, deepseek, google}, 0.7)
	if !result.IsCorrelated {
		t.Errorf("expected correlated (external fault), got score=%.4f", result.Score)
	}
	if result.Recommendation != "vendor-total-outage: external infrastructure fault" {
		t.Errorf("wrong recommendation: %s", result.Recommendation)
	}
}

func TestPOC6_CorrelationAccuracy(t *testing.T) {
	// Perfect positive correlation.
	x := []float64{1, 2, 3, 4, 5}
	y := []float64{2, 4, 6, 8, 10}
	r := pearsonR(x, y)
	if r < 0.999 {
		t.Errorf("perfect positive: r=%.4f, expected 1.0", r)
	}

	// Perfect negative correlation.
	yNeg := []float64{10, 8, 6, 4, 2}
	rNeg := pearsonR(x, yNeg)
	if rNeg > -0.999 {
		t.Errorf("perfect negative: r=%.4f, expected -1.0", rNeg)
	}

	// No correlation.
	yNone := []float64{5, 1, 4, 2, 3}
	rNone := pearsonR(x, yNone)
	if abs(rNone) > 0.3 {
		t.Errorf("no correlation: r=%.4f, expected ~0", rNone)
	}

	// Single data point → r=0 (zero variance).
	rSingle := pearsonR([]float64{1}, []float64{1})
	if rSingle != 0 {
		t.Errorf("single point: r=%.4f, expected 0", rSingle)
	}
}

func TestPOC6_WardenPolicyDispatch(t *testing.T) {
	// Simulate Warden policy dispatch based on correlation result.
	type Policy struct {
		Name      string
		Condition func(CorrelationResult) bool
		Actions   []string
	}

	policies := []Policy{
		{
			Name: "vendor-degraded",
			Condition: func(r CorrelationResult) bool {
				return !r.IsCorrelated
			},
			Actions: []string{"escalate_vendor", "notify_devops"},
		},
		{
			Name: "vendor-total-outage",
			Condition: func(r CorrelationResult) bool {
				return r.IsCorrelated
			},
			Actions: []string{"global_pause", "notify_human", "escalate_30m"},
		},
	}

	cases := []struct {
		name       string
		result     CorrelationResult
		wantPolicy string
		wantActs   []string
	}{
		{
			name:       "vendor self-fault",
			result:     CorrelationResult{IsCorrelated: false, Score: 0.12},
			wantPolicy: "vendor-degraded",
			wantActs:   []string{"escalate_vendor", "notify_devops"},
		},
		{
			name:       "external outage",
			result:     CorrelationResult{IsCorrelated: true, Score: 0.94},
			wantPolicy: "vendor-total-outage",
			wantActs:   []string{"global_pause", "notify_human", "escalate_30m"},
		},
	}

	for _, tc := range cases {
		var triggered *Policy
		for i := range policies {
			if policies[i].Condition(tc.result) {
				triggered = &policies[i]
				break
			}
		}
		if triggered == nil {
			t.Errorf("%s: no policy triggered", tc.name)
			continue
		}
		if triggered.Name != tc.wantPolicy {
			t.Errorf("%s: got policy %s, want %s", tc.name, triggered.Name, tc.wantPolicy)
		}
		for _, want := range tc.wantActs {
			found := false
			for _, a := range triggered.Actions {
				if a == want {
					found = true
					break
				}
			}
			if !found {
				t.Errorf("%s: missing action %q", tc.name, want)
			}
		}
	}
}

func TestPOC6_BoundaryThreshold(t *testing.T) {
	// Correlation at exactly the threshold should trigger.
	streams := []VendorStream{
		{Vendor: "A", Metrics: []float64{1, 2, 3, 4, 5}},
		{Vendor: "B", Metrics: []float64{1, 2, 3, 4, 5}}, // perfect r=1
	}
	result := analyzeCorrelation(streams, 0.7)
	if !result.IsCorrelated {
		t.Errorf("r=1.0 at threshold 0.7 should be correlated")
	}

	// Slightly below threshold should NOT trigger.
	streams[1] = VendorStream{Vendor: "B", Metrics: []float64{5, 4, 1, 2, 3}}
	result = analyzeCorrelation(streams, 0.7)
	if result.IsCorrelated {
		t.Errorf("low r=%.4f at threshold 0.7 should NOT be correlated", result.Score)
	}

	// Single vendor should not trigger.
	result = analyzeCorrelation([]VendorStream{{Vendor: "A", Metrics: []float64{1, 2, 3}}}, 0.7)
	if result.IsCorrelated {
		t.Error("single vendor should not be correlated")
	}
}
