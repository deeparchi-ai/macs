// POC-2: Agent Crash → Recovery → Replay
//
// The most complex POC: agent crashes mid-task, system detects failure,
// broadcasts, restores context from Curator, replays from Loom fork-point,
// and escalates on crash-loop detection.
//
//   Step 1 — Normal execution: agent runs 3-step task chain (A→B→C)
//   Step 2 — Crash detection: Warden no heartbeat for 5s → Relay broadcast
//   Step 3 — Recovery: Curator Tier 0 restore → Loom fork-point replay → retry Step C
//   Step 4 — Crash loop: 3 crashes in 5min → Warden escalation chain
//
// Coverage: §12 Warden + §11 Relay + §7 Curator + §3b Loom + §4 Chronicle
package poc

import (
	"fmt"
	"sync"
	"testing"
	"time"
)

// ── Curator: Tiered Context Store ──

type ContextTier int

const (
	Tier0Hot  ContextTier = iota // full fidelity, ~50K tokens
	Tier1Warm                    // summarized, key decisions, ~10K tokens
	Tier2Cold                    // bullet-point index, ~1K tokens
)

type AgentContext struct {
	AgentID    string
	Tier       ContextTier
	FullData   map[string]string // Tier 0: full data
	Summary    string            // Tier 1: summary
	Index      []string          // Tier 2: key topics
	ForkPoints map[string]string // step → snapshot
}

type Curator struct {
	mu     sync.RWMutex
	store  map[string]*AgentContext // agentID → context
}

func NewCurator() *Curator {
	return &Curator{store: make(map[string]*AgentContext)}
}

func (c *Curator) Save(ctx *AgentContext) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.store[ctx.AgentID] = ctx
}

func (c *Curator) Restore(agentID string) (*AgentContext, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	ctx, ok := c.store[agentID]
	return ctx, ok
}

// ── Loom: Fork-point Management ──

type ForkPoint struct {
	Step      string
	Snapshot  map[string]string // agent state at fork point
	Timestamp time.Time
}

type LoomManager struct {
	mu         sync.RWMutex
	forkPoints map[string][]ForkPoint // agentID → fork points
}

func NewLoomManager() *LoomManager {
	return &LoomManager{forkPoints: make(map[string][]ForkPoint)}
}

func (lm *LoomManager) SaveForkPoint(agentID, step string, state map[string]string) {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	lm.forkPoints[agentID] = append(lm.forkPoints[agentID], ForkPoint{
		Step:      step,
		Snapshot:  state,
		Timestamp: time.Now(),
	})
}

func (lm *LoomManager) LastForkPoint(agentID string) (*ForkPoint, bool) {
	lm.mu.RLock()
	defer lm.mu.RUnlock()
	fps, ok := lm.forkPoints[agentID]
	if !ok || len(fps) == 0 {
		return nil, false
	}
	last := fps[len(fps)-1]
	return &last, true
}

func (lm *LoomManager) ReplayFrom(agentID, fromStep string) (map[string]string, bool) {
	lm.mu.RLock()
	defer lm.mu.RUnlock()
	fps, ok := lm.forkPoints[agentID]
	if !ok {
		return nil, false
	}
	// Find the fork point for fromStep.
	for i := len(fps) - 1; i >= 0; i-- {
		if fps[i].Step == fromStep {
			return fps[i].Snapshot, true
		}
	}
	return nil, false
}

// ── Warden: Crash Detector ──

type CrashDetector struct {
	mu         sync.RWMutex
	heartbeats map[string]time.Time
	failures   map[string][]time.Time
	window     time.Duration
}

func NewCrashDetector(loopWindow time.Duration) *CrashDetector {
	return &CrashDetector{
		heartbeats: make(map[string]time.Time),
		failures:   make(map[string][]time.Time),
		window:     loopWindow,
	}
}

func (cd *CrashDetector) Heartbeat(agentID string) {
	cd.mu.Lock()
	defer cd.mu.Unlock()
	cd.heartbeats[agentID] = time.Now()
}

func (cd *CrashDetector) Check(agentID string, timeout time.Duration) bool {
	cd.mu.RLock()
	defer cd.mu.RUnlock()
	last, ok := cd.heartbeats[agentID]
	if !ok {
		return true // never seen → crash
	}
	return time.Since(last) > timeout
}

func (cd *CrashDetector) RecordFailure(agentID string) bool {
	cd.mu.Lock()
	defer cd.mu.Unlock()
	now := time.Now()
	cd.failures[agentID] = append(cd.failures[agentID], now)

	// Prune old failures.
	cutoff := now.Add(-cd.window)
	recent := make([]time.Time, 0)
	for _, t := range cd.failures[agentID] {
		if t.After(cutoff) {
			recent = append(recent, t)
		}
	}
	cd.failures[agentID] = recent
	return len(recent) >= 3
}

// ── Chronicle: Audit Trail ──

type AuditLog struct {
	mu      sync.Mutex
	entries []string
}

func NewAuditLog() *AuditLog { return &AuditLog{} }

func (a *AuditLog) Record(event string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.entries = append(a.entries, fmt.Sprintf("[%s] %s", time.Now().Format("15:04:05"), event))
}

func (a *AuditLog) Count() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	return len(a.entries)
}

// ── Agent Simulator ──

type ResearchAgent struct {
	ID      string
	Steps   []string        // task steps A, B, C
	State   map[string]string
	Current int             // -1 = not started
	Failing bool            // simulate crash at next step
}

func NewResearchAgent(id string) *ResearchAgent {
	return &ResearchAgent{
		ID:      id,
		Steps:   []string{"A-search", "B-analyze", "C-report"},
		State:   make(map[string]string),
		Current: -1,
	}
}

func (a *ResearchAgent) ExecuteStep() (string, error) {
	if a.Failing {
		return "", fmt.Errorf("agent crashed")
	}
	a.Current++
	if a.Current >= len(a.Steps) {
		return "", fmt.Errorf("all steps complete")
	}
	step := a.Steps[a.Current]
	a.State[step] = "completed"
	return step, nil
}

// ── POC-2 Tests ──

func TestPOC2_Step1_NormalExecution(t *testing.T) {
	agent := NewResearchAgent("research.prod")
	curator := NewCurator()
	loom := NewLoomManager()
	audit := NewAuditLog()

	steps := []string{}
	for {
		step, err := agent.ExecuteStep()
		if err != nil {
			break
		}
		steps = append(steps, step)

		// Loom: save fork-point after each step.
		loom.SaveForkPoint(agent.ID, step, copyMap(agent.State))

		audit.Record(agent.ID + ":" + step + " completed")
	}

	if len(steps) != 3 {
		t.Errorf("expected 3 steps, got %d: %v", len(steps), steps)
	}

	// Curator: save full context (Tier 0).
	curator.Save(&AgentContext{
		AgentID:    agent.ID,
		Tier:       Tier0Hot,
		FullData:   agent.State,
		ForkPoints: map[string]string{"B-analyze": "snapshot-at-B"},
	})

	if audit.Count() != 3 {
		t.Errorf("expected 3 audit entries, got %d", audit.Count())
	}
}

func TestPOC2_Step2_CrashDetection(t *testing.T) {
	detector := NewCrashDetector(5 * time.Minute)
	bus := NewBroadcastBus()
	audit := NewAuditLog()

	// Agent registers heartbeat.
	detector.Heartbeat("research.prod")

	// Track broadcasts.
	var broadcasts []string
	bus.Subscribe("agent-crashed", func(eventType, source string) {
		broadcasts = append(broadcasts, source)
	})

	// Simulate crash: agent stops heartbeating.
	time.Sleep(10 * time.Millisecond)
	if !detector.Check("research.prod", 5*time.Millisecond) {
		t.Error("should detect crash after timeout")
	}

	// Record failure → check crash loop.
	isLoop := detector.RecordFailure("research.prod")
	if isLoop {
		t.Error("single failure should not trigger crash loop")
	}

	// Broadcast crash.
	bus.Publish("agent-crashed", "research.prod")
	audit.Record("warden:agent-crashed research.prod")

	if len(broadcasts) != 1 || broadcasts[0] != "research.prod" {
		t.Errorf("broadcasts: %v", broadcasts)
	}
}

func TestPOC2_Step3_RecoveryAndReplay(t *testing.T) {
	curator := NewCurator()
	loom := NewLoomManager()

	// Pre-save agent state.
	agentState := map[string]string{
		"A-search":  "completed",
		"B-analyze": "completed",
	}
	loom.SaveForkPoint("research.prod", "A-search", map[string]string{"A-search": "completed"})
	loom.SaveForkPoint("research.prod", "B-analyze", agentState)

	curator.Save(&AgentContext{
		AgentID:  "research.prod",
		Tier:     Tier0Hot,
		FullData: agentState,
	})

	// Agent crashes at step C. Recovery:
	// 1. Curator restores hot context.
	ctx, ok := curator.Restore("research.prod")
	if !ok {
		t.Fatal("curator restore failed")
	}
	if ctx.Tier != Tier0Hot {
		t.Errorf("expected Tier0Hot, got %d", ctx.Tier)
	}

	// 2. Loom replays from fork-point B-analyze.
	snapshot, ok := loom.ReplayFrom("research.prod", "B-analyze")
	if !ok {
		t.Fatal("loom replay failed")
	}
	if snapshot["A-search"] != "completed" || snapshot["B-analyze"] != "completed" {
		t.Errorf("snapshot incomplete: %v", snapshot)
	}

	// 3. Retry step C.
	// (In real system, the agent re-executes C with restored context.)
	restoredAgent := NewResearchAgent("research.prod")
	restoredAgent.State = snapshot
	restoredAgent.Current = 1 // resume at step B (C next)

	// Execute the remaining step.
	step, err := restoredAgent.ExecuteStep()
	if err != nil {
		t.Fatalf("step C failed: %v", err)
	}
	if step != "C-report" {
		t.Errorf("expected C-report, got %s", step)
	}
}

func TestPOC2_Step4_CrashLoopEscalation(t *testing.T) {
	detector := NewCrashDetector(5 * time.Minute)
	audit := NewAuditLog()

	// Simulate 3 crashes in rapid succession.
	for i := 0; i < 3; i++ {
		isLoop := detector.RecordFailure("research.prod")
		if i < 2 && isLoop {
			t.Errorf("crash %d: should not trigger loop yet", i+1)
		}
		if i == 2 && !isLoop {
			t.Error("3rd crash should trigger crash loop")
		}
		audit.Record(fmt.Sprintf("warden:crash-%d research.prod", i+1))
	}

	// Warden policy: crash-loop → suspend agent + escalate.
	// (The POC-5 escalation chain would apply here.)
	if audit.Count() != 3 {
		t.Errorf("expected 3 audit entries, got %d", audit.Count())
	}
}

func TestPOC2_TieredContextRestore(t *testing.T) {
	curator := NewCurator()

	// Save contexts at all three tiers.
	curator.Save(&AgentContext{
		AgentID: "agent-x", Tier: Tier0Hot,
		FullData: map[string]string{"data": "full fidelity"},
	})
	curator.Save(&AgentContext{
		AgentID: "agent-x-summary", Tier: Tier1Warm,
		Summary: "key decisions preserved",
	})
	curator.Save(&AgentContext{
		AgentID: "agent-x-index", Tier: Tier2Cold,
		Index: []string{"topic1", "topic2"},
	})

	// Restore Tier 0.
	ctx, ok := curator.Restore("agent-x")
	if !ok || ctx.Tier != Tier0Hot {
		t.Error("Tier 0 restore failed")
	}

	// Restore Tier 1.
	ctx, ok = curator.Restore("agent-x-summary")
	if !ok || ctx.Summary != "key decisions preserved" {
		t.Error("Tier 1 restore failed")
	}

	// Restore Tier 2.
	ctx, ok = curator.Restore("agent-x-index")
	if !ok || len(ctx.Index) != 2 {
		t.Error("Tier 2 restore failed")
	}
}

func TestPOC2_ForkPointReplayAccuracy(t *testing.T) {
	loom := NewLoomManager()

	// Save fork points for a 5-step pipeline.
	steps := []string{"init", "fetch", "process", "validate", "deliver"}
	state := make(map[string]string)
	for _, s := range steps {
		state[s] = "done"
		loom.SaveForkPoint("agent-pipe", s, copyMap(state))
	}

	// Crash after "process" — replay from "fetch".
	snapshot, ok := loom.ReplayFrom("agent-pipe", "fetch")
	if !ok {
		t.Fatal("replay from fetch failed")
	}
	if len(snapshot) != 2 { // init, fetch
		t.Errorf("expected 2 steps in snapshot, got %d: %v", len(snapshot), snapshot)
	}
	if snapshot["init"] != "done" || snapshot["fetch"] != "done" {
		t.Errorf("snapshot incomplete")
	}

	// "validate" and "deliver" should NOT be in snapshot.
	if _, exists := snapshot["validate"]; exists {
		t.Error("validate should not be in fetch snapshot")
	}
}

func TestPOC2_DUMPArtifact(t *testing.T) {
	// DUMP: frozen snapshot of agent's decision chain before recovery.
	loom := NewLoomManager()
	curator := NewCurator()

	agentState := map[string]string{
		"A-search":  "completed: found 5 sources",
		"B-analyze": "completed: identified 3 patterns",
	}
	loom.SaveForkPoint("research.prod", "B-analyze", copyMap(agentState))
	curator.Save(&AgentContext{
		AgentID:  "research.prod",
		Tier:     Tier0Hot,
		FullData: agentState,
	})

	// DUMP = Curator snapshot + Loom last fork point.
	ctx, _ := curator.Restore("research.prod")
	fp, _ := loom.LastForkPoint("research.prod")

	if ctx.FullData["A-search"] == "" {
		t.Error("DUMP: curator data missing")
	}
	if fp.Step != "B-analyze" {
		t.Errorf("DUMP: wrong fork point %s", fp.Step)
	}

	// DUMP is self-consistent.
	if len(ctx.FullData) != len(fp.Snapshot) {
		t.Errorf("DUMP inconsistency: curator=%d, loom=%d", len(ctx.FullData), len(fp.Snapshot))
	}
}

// ── Helpers ──

func copyMap(m map[string]string) map[string]string {
	c := make(map[string]string, len(m))
	for k, v := range m {
		c[k] = v
	}
	return c
}
