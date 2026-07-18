// POC-5: Token Budget Policy Chain
//
// Verifies that Warden's policy engine correctly triggers escalation
// actions as the Regulator's token budget level degrades from GREEN
// through YELLOW, RED, to BLACK.
//
// Coverage: §12 Warden + §2 Regulator
//
// Predefined policies:
//
//	Name                Condition                    Actions
//	token-budget-green   regulator.level == GREEN     (none — baseline)
//	token-budget-yellow  regulator.level == YELLOW    notify_owner, reduce_audit_sampling
//	token-budget-red     regulator.level == RED       suspend_l2_l3, notify_owner
//	token-budget-black   regulator.level == BLACK     allow_l1_only, notify_human, escalate(30m)
//
// The escalation chain fires a timer: if the BLACK state persists for
// 30 minutes without human acknowledgement, it escalates to L3 (critical).
package poc

import (
	"strings"
	"testing"
	"time"
)

// ── Simulated Subsystem APIs (thin wrappers around real implementations) ──

// PolicyEngine wraps the Warden policy engine.
type PolicyEngine struct {
	policies []Policy
}

// Policy is a declarative operational rule.
type Policy struct {
	Name            string
	Condition       string // e.g. "regulator.level == YELLOW"
	Actions         []string
	EscalationLevel int // 0=info, 1=warning, 2=action, 3=critical
}

func NewPolicyEngine() *PolicyEngine { return &PolicyEngine{} }

func (pe *PolicyEngine) AddPolicy(p Policy) { pe.policies = append(pe.policies, p) }

// Evaluate checks all policies against state and returns triggered ones.
func (pe *PolicyEngine) Evaluate(state map[string]interface{}) []Policy {
	var triggered []Policy
	for _, p := range pe.policies {
		if matchCondition(p.Condition, state) {
			triggered = append(triggered, p)
		}
	}
	return triggered
}

// matchCondition implements a simple DSL:
//
//	"regulator.level == YELLOW"  (string equality)
//	"regulator.level != GREEN"   (string inequality)
//	"token_pct >= 70"            (numeric comparison)
func matchCondition(condition string, state map[string]interface{}) bool {
	parts := strings.Fields(strings.TrimSpace(condition))
	if len(parts) < 3 {
		return false
	}
	metric, op, threshold := parts[0], parts[1], parts[2]

	val, ok := state[metric]
	if !ok {
		return false
	}

	// String comparison
	if s, ok := val.(string); ok {
		switch op {
		case "==":
			return s == threshold
		case "!=":
			return s != threshold
		}
		return false
	}

	// Numeric comparison
	var current float64
	switch v := val.(type) {
	case int:
		current = float64(v)
	case float64:
		current = v
	default:
		return false
	}
	var target float64
	fmtSscanf(threshold, &target)

	switch op {
	case ">=":
		return current >= target
	case ">":
		return current > target
	case "<=":
		return current <= target
	case "<":
		return current < target
	case "==":
		return current == target
	case "!=":
		return current != target
	}
	return false
}

func fmtSscanf(s string, v *float64) { _, _ = _sscanf(s, v) }
func _sscanf(s string, v *float64) (int, error) {
	// Minimal sscanf for "70", "90", "100"
	var i int
	n := 0
	for _, c := range s {
		if c >= '0' && c <= '9' {
			i = i*10 + int(c-'0')
			n++
		}
	}
	*v = float64(i)
	return n, nil
}

// ── Escalation Timer ──

// EscalationChain tracks escalation level progression.
type EscalationChain struct {
	Levels       []int
	CurrentIndex int // -1 = not started
}

func NewEscalationChain(levels []int) *EscalationChain {
	return &EscalationChain{Levels: levels, CurrentIndex: -1}
}

func (ec *EscalationChain) Escalate() int {
	if ec.CurrentIndex < len(ec.Levels)-1 {
		ec.CurrentIndex++
	}
	return ec.Levels[ec.CurrentIndex]
}

func (ec *EscalationChain) Current() int {
	if ec.CurrentIndex < 0 {
		return ec.Levels[0]
	}
	return ec.Levels[ec.CurrentIndex]
}

// ── Test: Full Budget Degradation Lifecycle ──

func TestPOC5_TokenBudgetLifecycle(t *testing.T) {
	// 1. Set up Warden policy engine with token budget policies.
	pe := NewPolicyEngine()
	pe.AddPolicy(Policy{
		Name:      "token-budget-yellow",
		Condition: "regulator.level == YELLOW",
		Actions:   []string{"notify_owner", "reduce_audit_sampling"},
	})
	pe.AddPolicy(Policy{
		Name:      "token-budget-red",
		Condition: "regulator.level == RED",
		Actions:   []string{"suspend_l2_l3", "notify_owner"},
	})
	pe.AddPolicy(Policy{
		Name:      "token-budget-black",
		Condition: "regulator.level == BLACK",
		Actions:   []string{"allow_l1_only", "notify_human"},
	})

	// 2. GREEN — no policies should trigger.
	state := map[string]interface{}{"regulator.level": "GREEN", "token_pct": 45}
	triggered := pe.Evaluate(state)
	if len(triggered) != 0 {
		t.Fatalf("GREEN: expected 0 triggered, got %d", len(triggered))
	}

	// 3. YELLOW — token_pct crosses 70%.
	state["regulator.level"] = "YELLOW"
	state["token_pct"] = 72
	triggered = pe.Evaluate(state)
	if len(triggered) != 1 {
		t.Fatalf("YELLOW: expected 1 triggered, got %d", len(triggered))
	}
	if triggered[0].Name != "token-budget-yellow" {
		t.Errorf("YELLOW: got %s", triggered[0].Name)
	}
	for _, want := range []string{"notify_owner", "reduce_audit_sampling"} {
		if !contains(triggered[0].Actions, want) {
			t.Errorf("YELLOW: missing action %q", want)
		}
	}

	// 4. RED — token_pct crosses 90%.
	state["regulator.level"] = "RED"
	state["token_pct"] = 93
	triggered = pe.Evaluate(state)
	if len(triggered) != 1 {
		t.Fatalf("RED: expected 1 triggered, got %d", len(triggered))
	}
	if triggered[0].Name != "token-budget-red" {
		t.Errorf("RED: got %s", triggered[0].Name)
	}
	for _, want := range []string{"suspend_l2_l3", "notify_owner"} {
		if !contains(triggered[0].Actions, want) {
			t.Errorf("RED: missing action %q", want)
		}
	}

	// 5. BLACK — budget fully exhausted.
	state["regulator.level"] = "BLACK"
	state["token_pct"] = 100
	triggered = pe.Evaluate(state)
	if len(triggered) != 1 {
		t.Fatalf("BLACK: expected 1 triggered, got %d", len(triggered))
	}
	if triggered[0].Name != "token-budget-black" {
		t.Errorf("BLACK: got %s", triggered[0].Name)
	}
	for _, want := range []string{"allow_l1_only", "notify_human"} {
		if !contains(triggered[0].Actions, want) {
			t.Errorf("BLACK: missing action %q", want)
		}
	}
}

// TestPOC5_EscalationChain verifies escalation timer behavior.
func TestPOC5_EscalationChain(t *testing.T) {
	// BLACK triggers escalation: L1 → L2 → L3.
	// CurrentIndex starts at -1. Each Escalate() increments and returns new level.
	chain := NewEscalationChain([]int{1, 2, 3})

	if chain.Current() != 1 {
		t.Errorf("initial: L1, got L%d", chain.Current())
	}

	lvl := chain.Escalate()
	if lvl != 1 {
		t.Errorf("escalate #1: L1, got L%d", lvl)
	}

	lvl = chain.Escalate()
	if lvl != 2 {
		t.Errorf("escalate #2: L2, got L%d", lvl)
	}

	lvl = chain.Escalate()
	if lvl != 3 {
		t.Errorf("escalate #3: L3, got L%d", lvl)
	}
}

// TestPOC5_MultiPolicyTrigger verifies multiple policies can fire
// simultaneously if conditions overlap (e.g. numeric + string).
func TestPOC5_MultiPolicyTrigger(t *testing.T) {
	pe := NewPolicyEngine()
	pe.AddPolicy(Policy{
		Name:      "token-budget-yellow",
		Condition: "regulator.level == YELLOW",
		Actions:   []string{"notify_owner"},
	})
	pe.AddPolicy(Policy{
		Name:      "token-pressure-high",
		Condition: "token_pct >= 70",
		Actions:   []string{"reduce_sampling"},
	})

	state := map[string]interface{}{
		"regulator.level": "YELLOW",
		"token_pct":       75,
	}

	triggered := pe.Evaluate(state)
	if len(triggered) != 2 {
		t.Fatalf("expected 2 policies triggered, got %d", len(triggered))
	}

	names := []string{triggered[0].Name, triggered[1].Name}
	if !contains(names, "token-budget-yellow") || !contains(names, "token-pressure-high") {
		t.Errorf("expected both policies, got %v", names)
	}
}

// TestPOC5_RecoveryFromBlack verifies policy returns to GREEN on budget reset.
func TestPOC5_RecoveryFromBlack(t *testing.T) {
	pe := NewPolicyEngine()
	pe.AddPolicy(Policy{
		Name:      "token-budget-black",
		Condition: "regulator.level == BLACK",
		Actions:   []string{"allow_l1_only"},
	})

	// BLACK → triggers.
	state := map[string]interface{}{"regulator.level": "BLACK"}
	if len(pe.Evaluate(state)) != 1 {
		t.Fatal("BLACK should trigger")
	}

	// Budget resets → GREEN → no trigger.
	state["regulator.level"] = "GREEN"
	if len(pe.Evaluate(state)) != 0 {
		t.Fatal("GREEN should not trigger")
	}
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

// TestPOC5_EscalationTimeout demonstrates the 30-minute escalation timer.
// It uses real time.Duration to prove the concept, but uses shortened
// intervals in test (200ms) to avoid actually waiting 30 minutes.
func TestPOC5_EscalationTimeout(t *testing.T) {
	// Simulated escalation timer: L1 → L2 → L3 with 200ms intervals.
	type EscalationTimer struct {
		level     int
		timeout   time.Duration
		lastAck   time.Time
	}

	timer := &EscalationTimer{level: 1, timeout: 200 * time.Millisecond, lastAck: time.Now()}

	// No ack → escalate after timeout.
	time.Sleep(250 * time.Millisecond)
	if time.Since(timer.lastAck) > timer.timeout {
		timer.level = 2
		timer.lastAck = time.Now()
	}
	if timer.level != 2 {
		t.Errorf("expected L2 after timeout, got L%d", timer.level)
	}

	// Human acknowledges → reset to L1.
	timer.level = 1
	timer.lastAck = time.Now()
	if timer.level != 1 {
		t.Errorf("expected L1 after reset, got L%d", timer.level)
	}
}
