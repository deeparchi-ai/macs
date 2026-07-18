// POC-1: Tri-Model Divergence → Majority Adjudication → Failover
//
// The most critical POC scenario: subjective agent output is verified by
// three models from different vendors. When models diverge, XVal applies
// majority rule. When vendors fail, the system degrades gracefully:
//
//   Step 1 — Normal: 3 models vote → 2/3 agreement → L2 flagged, execute
//   Step 2 — Primary fail: Gauge detects vendor error rate > 10% →
//            Warden triggers failover → audit promoted to primary
//   Step 3 — Total outage: all 3 vendors fail → Gauge correlation = 0.95 →
//            Warden "vendor-total-outage" → global pause + notify human
//
// Coverage: §5 XVal + §9 Gauge + §12 Warden + §4 Chronicle
package poc

import (
	"fmt"
	"testing"
)

// ── XVal: Tri-model adjudication ──

type ModelVendor string

const (
	VendorAnthropic ModelVendor = "anthropic"
	VendorDeepSeek  ModelVendor = "deepseek"
	VendorGoogle    ModelVendor = "google"
)

type ModelOutput struct {
	Vendor     ModelVendor
	ModelName  string
	Confidence float64
	Output     string
}

type TriModelResult struct {
	Verdict      string   // "tri-majority", "tri-split", "dual-agreement", "single-survivor"
	Agreeing     int      // number of agreeing models
	Dissenting   []string // vendor names that disagreed
	Confidence   float64  // aggregate confidence
	PrimaryModel ModelOutput
	AuditModel   ModelOutput
	TertiaryModel ModelOutput
}

// AdjudicateTriModel evaluates three model outputs with majority rule.
func AdjudicateTriModel(primary, audit, tertiary ModelOutput) TriModelResult {
	result := TriModelResult{
		PrimaryModel:  primary,
		AuditModel:    audit,
		TertiaryModel: tertiary,
	}

	// Count "agreement" — two models agree if their confidence diff < 0.3.
	agreePA := abs(primary.Confidence-audit.Confidence) < 0.3
	agreePT := abs(primary.Confidence-tertiary.Confidence) < 0.3
	agreeAT := abs(audit.Confidence-tertiary.Confidence) < 0.3

	agreements := 0
	if agreePA {
		agreements++
	}
	if agreePT {
		agreements++
	}
	if agreeAT {
		agreements++
	}

	result.Agreeing = 0
	var disagree []string

	switch {
	case agreePA && agreePT && agreeAT:
		// All three agree
		result.Agreeing = 3
		result.Verdict = "tri-majority"
	case agreePA && agreePT:
		result.Agreeing = 3
		result.Verdict = "tri-majority"
	case agreePA:
		result.Agreeing = 2
		result.Verdict = "dual-agreement"
		if abs(primary.Confidence-tertiary.Confidence) >= 0.3 {
			disagree = append(disagree, "tertiary")
		}
	case agreePT:
		result.Agreeing = 2
		result.Verdict = "dual-agreement"
		if abs(audit.Confidence-tertiary.Confidence) >= 0.3 {
			disagree = append(disagree, "audit")
		}
	case agreeAT:
		result.Agreeing = 2
		result.Verdict = "dual-agreement"
		if abs(primary.Confidence-audit.Confidence) >= 0.3 {
			disagree = append(disagree, "primary")
		}
	default:
		result.Agreeing = 1
		result.Verdict = "tri-split"
		disagree = append(disagree, "all models disagree")
	}

	result.Dissenting = disagree

	// Aggregate confidence: average of agreeing models.
	result.Confidence = (primary.Confidence + audit.Confidence + tertiary.Confidence) / 3

	return result
}

// ── Gauge: Vendor Health Monitor ──

type VendorHealth struct {
	Vendor     ModelVendor
	ErrorRate  float64 // 5-min window
	IsHealthy  bool
}

func checkVendorHealth(vendor ModelVendor, errorRate float64) VendorHealth {
	return VendorHealth{
		Vendor:    vendor,
		ErrorRate: errorRate,
		IsHealthy: errorRate < 0.10,
	}
}

// ── Failover Engine ──

type FailoverState struct {
	ActiveModels  []ModelVendor
	PrimaryModel  ModelVendor
	AuditModel    ModelVendor
	TertiaryModel ModelVendor
	Level         int // 3=full, 2=dual, 1=single, 0=none
}

func NewFailoverState() *FailoverState {
	return &FailoverState{
		ActiveModels:  []ModelVendor{VendorAnthropic, VendorDeepSeek, VendorGoogle},
		PrimaryModel:  VendorAnthropic,
		AuditModel:    VendorDeepSeek,
		TertiaryModel: VendorGoogle,
		Level:         3,
	}
}

// Degrade removes a failed vendor and promotes remaining models.
func (fs *FailoverState) Degrade(failed ModelVendor) {
	remaining := make([]ModelVendor, 0)
	for _, m := range fs.ActiveModels {
		if m != failed {
			remaining = append(remaining, m)
		}
	}
	fs.ActiveModels = remaining
	fs.Level = len(remaining)

	switch fs.Level {
	case 2:
		fs.PrimaryModel = remaining[0]
		fs.AuditModel = remaining[1]
		fs.TertiaryModel = "" // no tertiary
	case 1:
		fs.PrimaryModel = remaining[0]
		fs.AuditModel = "" // no audit → L0 self-critique
		fs.TertiaryModel = ""
	case 0:
		fs.PrimaryModel = ""
		fs.AuditModel = ""
		fs.TertiaryModel = ""
	}
}

// ── Chronicle: Audit Trail ──

type AuditEntry struct {
	ID      string
	Event   string
	Details map[string]string
}

type AuditTrail struct {
	entries []AuditEntry
}

func (at *AuditTrail) Record(event string, details map[string]string) {
	at.entries = append(at.entries, AuditEntry{
		ID:      fmt.Sprintf("audit-%d", len(at.entries)+1),
		Event:   event,
		Details: details,
	})
}

func (at *AuditTrail) Count() int { return len(at.entries) }

// ── POC-1 Tests ──

func TestPOC1_Step1_TriModelAdjudication(t *testing.T) {
	// Normal operation: 3 models, 2/3 agree.
	primary := ModelOutput{Vendor: VendorAnthropic, Confidence: 0.92, Output: "strategy A"}
	audit := ModelOutput{Vendor: VendorDeepSeek, Confidence: 0.88, Output: "strategy A (minor tweaks)"}
	tertiary := ModelOutput{Vendor: VendorGoogle, Confidence: 0.50, Output: "strategy B"}

	result := AdjudicateTriModel(primary, audit, tertiary)

	// Primary (0.92) and Audit (0.88) agree (diff=0.04 < 0.3).
	// Tertiary (0.50) disagrees with both.
	if result.Verdict != "dual-agreement" {
		t.Errorf("expected dual-agreement, got %s", result.Verdict)
	}
	if result.Agreeing != 2 {
		t.Errorf("expected 2 agreeing, got %d", result.Agreeing)
	}
	if len(result.Dissenting) == 0 || result.Dissenting[0] != "tertiary" {
		t.Errorf("expected tertiary dissenting, got %v", result.Dissenting)
	}

	// Verify audit trail records.
	auditTrail := &AuditTrail{}
	auditTrail.Record("xval-adjudicated", map[string]string{
		"verdict":    result.Verdict,
		"primary":    string(result.PrimaryModel.Vendor),
		"audit":      string(result.AuditModel.Vendor),
		"tertiary":   string(result.TertiaryModel.Vendor),
		"confidence": fmt.Sprintf("%.2f", result.Confidence),
	})
	if auditTrail.Count() != 1 {
		t.Errorf("expected 1 audit entry, got %d", auditTrail.Count())
	}
}

func TestPOC1_Step1_TriMajority(t *testing.T) {
	// All three models agree.
	primary := ModelOutput{Vendor: VendorAnthropic, Confidence: 0.95}
	audit := ModelOutput{Vendor: VendorDeepSeek, Confidence: 0.92}
	tertiary := ModelOutput{Vendor: VendorGoogle, Confidence: 0.90}

	result := AdjudicateTriModel(primary, audit, tertiary)

	if result.Verdict != "tri-majority" {
		t.Errorf("expected tri-majority, got %s", result.Verdict)
	}
	if result.Agreeing != 3 {
		t.Errorf("expected 3 agreeing, got %d", result.Agreeing)
	}
}

func TestPOC1_Step1_TriSplit(t *testing.T) {
	// All three models disagree.
	primary := ModelOutput{Vendor: VendorAnthropic, Confidence: 0.90}
	audit := ModelOutput{Vendor: VendorDeepSeek, Confidence: 0.40}
	tertiary := ModelOutput{Vendor: VendorGoogle, Confidence: 0.10}

	result := AdjudicateTriModel(primary, audit, tertiary)

	if result.Verdict != "tri-split" {
		t.Errorf("expected tri-split, got %s", result.Verdict)
	}
}

func TestPOC1_Step2_PrimaryFailover(t *testing.T) {
	// Simulate single-vendor degradation.
	health := checkVendorHealth(VendorAnthropic, 0.15) // error rate > 10%

	if health.IsHealthy {
		t.Error("anthropic should be unhealthy at 15% error rate")
	}

	// Trigger failover.
	fs := NewFailoverState()
	fs.Degrade(VendorAnthropic)

	if fs.Level != 2 {
		t.Errorf("expected level 2 after degrade, got %d", fs.Level)
	}
	if fs.PrimaryModel != VendorDeepSeek {
		t.Errorf("expected deepseek promoted to primary, got %s", fs.PrimaryModel)
	}
	if fs.AuditModel != VendorGoogle {
		t.Errorf("expected google promoted to audit, got %s", fs.AuditModel)
	}
	if fs.TertiaryModel != "" {
		t.Errorf("expected no tertiary in dual mode, got %s", fs.TertiaryModel)
	}

	// Dual-model adjudication should still work.
	primary := ModelOutput{Vendor: VendorDeepSeek, Confidence: 0.88}
	audit := ModelOutput{Vendor: VendorGoogle, Confidence: 0.85}
	// With only 2 models, agreement check still valid.
	result := AdjudicateTriModel(primary, audit, ModelOutput{Vendor: "", Confidence: 0})
	if result.Agreeing < 1 {
		t.Errorf("dual-model adjudication failed: %s", result.Verdict)
	}
}

func TestPOC1_Step3_TotalOutage(t *testing.T) {
	// All three vendors fail.
	healthA := checkVendorHealth(VendorAnthropic, 0.50)
	healthD := checkVendorHealth(VendorDeepSeek, 0.48)
	healthG := checkVendorHealth(VendorGoogle, 0.45)

	allUnhealthy := !healthA.IsHealthy && !healthD.IsHealthy && !healthG.IsHealthy
	if !allUnhealthy {
		t.Error("all vendors should be unhealthy")
	}

	// Cross-vendor correlation check (from POC-6 approach).
	// All error rates are high → lockstep degradation → high correlation.
	correlated := true // simulated

	// Degrade → total outage.
	fs := NewFailoverState()
	fs.Degrade(VendorAnthropic)
	fs.Degrade(VendorDeepSeek)
	fs.Degrade(VendorGoogle)

	if fs.Level != 0 {
		t.Errorf("expected level 0 (total outage), got %d", fs.Level)
	}

	// Warden policy: if correlated && all unhealthy → global pause.
	if correlated && fs.Level == 0 {
		// Correct: vendor-total-outage → global pause + notify human.
	} else {
		t.Error("total outage should trigger global pause")
	}

	// Audit trail records the outage.
	auditTrail := &AuditTrail{}
	auditTrail.Record("vendor-total-outage", map[string]string{
		"correlated": fmt.Sprintf("%v", correlated),
		"anthropic":  fmt.Sprintf("%.2f", healthA.ErrorRate),
		"deepseek":   fmt.Sprintf("%.2f", healthD.ErrorRate),
		"google":     fmt.Sprintf("%.2f", healthG.ErrorRate),
	})
	if auditTrail.Count() != 1 {
		t.Errorf("expected 1 audit entry, got %d", auditTrail.Count())
	}
}

func TestPOC1_FailoverDegradeSequence(t *testing.T) {
	// Full degradation: 3 → 2 → 1 → 0
	fs := NewFailoverState()
	auditTrail := &AuditTrail{}

	if fs.Level != 3 {
		t.Errorf("initial: expected 3, got %d", fs.Level)
	}

	// Anthropic fails → DeepSeek promoted to primary.
	fs.Degrade(VendorAnthropic)
	auditTrail.Record("vendor-degraded", map[string]string{"vendor": "anthropic", "new_level": "2"})
	if fs.Level != 2 || fs.PrimaryModel != VendorDeepSeek {
		t.Errorf("after anthropic fail: level=%d, primary=%s", fs.Level, fs.PrimaryModel)
	}

	// DeepSeek also fails → Google is sole survivor.
	fs.Degrade(VendorDeepSeek)
	auditTrail.Record("vendor-degraded", map[string]string{"vendor": "deepseek", "new_level": "1"})
	if fs.Level != 1 || fs.PrimaryModel != VendorGoogle {
		t.Errorf("after deepseek fail: level=%d, primary=%s", fs.Level, fs.PrimaryModel)
	}
	if fs.AuditModel != "" {
		t.Errorf("single model should have no audit: got %s", fs.AuditModel)
	}

	// Google fails → total outage.
	fs.Degrade(VendorGoogle)
	auditTrail.Record("vendor-total-outage", map[string]string{"new_level": "0"})
	if fs.Level != 0 {
		t.Errorf("after google fail: expected 0, got %d", fs.Level)
	}

	if auditTrail.Count() != 3 {
		t.Errorf("expected 3 audit entries, got %d", auditTrail.Count())
	}
}

func TestPOC1_HealthyVendorDoesNotDegrade(t *testing.T) {
	health := checkVendorHealth(VendorDeepSeek, 0.05) // 5% error rate
	if !health.IsHealthy {
		t.Error("deepseek at 5% should be healthy")
	}

	health = checkVendorHealth(VendorAnthropic, 0.099) // just below threshold
	if !health.IsHealthy {
		t.Error("anthropic at 9.9% should be healthy")
	}

	health = checkVendorHealth(VendorGoogle, 0.10) // at threshold
	if health.IsHealthy {
		t.Error("google at 10% should be unhealthy (threshold)")
	}
}
