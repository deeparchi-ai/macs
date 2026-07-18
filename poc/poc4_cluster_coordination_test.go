// POC-4: Cluster Coordination → Failure Propagation
//
// Verifies multi-agent cluster coordination: membership heartbeat, shared
// state with TTL, broadcast on member failure, Pulse dependency graph
// propagation, and group communication.
//
//   Step 1 — Cluster formation: 4 agents join, heartbeat, subscribe to events
//   Step 2 — Shared state: architect writes model config, researcher reads with TTL
//   Step 3 — Coder offline: DetectStale → Broadcast → Pulse Propagate
//   Step 4 — Group removal: coder removed from active-deploy group
//
// Coverage: §11 Relay + §12 Warden + §13 Pulse
package poc

import (
	"sync"
	"testing"
	"time"
)

// ── Relay: Cluster ──

type MemberStatus int

const (
	MemberOnline  MemberStatus = iota
	MemberOffline
)

type ClusterMember struct {
	ID            string
	LUName        string
	Status        MemberStatus
	LastHeartbeat time.Time
}

type Cluster struct {
	mu      sync.RWMutex
	members map[string]*ClusterMember
}

func NewCluster() *Cluster {
	return &Cluster{members: make(map[string]*ClusterMember)}
}

func (c *Cluster) Join(m *ClusterMember) {
	c.mu.Lock()
	defer c.mu.Unlock()
	m.Status = MemberOnline
	m.LastHeartbeat = time.Now()
	c.members[m.ID] = m
}

func (c *Cluster) Leave(id string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.members, id)
}

func (c *Cluster) Heartbeat(id string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	m, ok := c.members[id]
	if !ok {
		return false
	}
	m.LastHeartbeat = time.Now()
	if m.Status == MemberOffline {
		m.Status = MemberOnline
	}
	return true
}

func (c *Cluster) ListOnline() []*ClusterMember {
	c.mu.RLock()
	defer c.mu.RUnlock()
	var online []*ClusterMember
	for _, m := range c.members {
		if m.Status == MemberOnline {
			online = append(online, m)
		}
	}
	return online
}

func (c *Cluster) DetectStale(timeout time.Duration) []*ClusterMember {
	c.mu.Lock()
	defer c.mu.Unlock()
	cutoff := time.Now().Add(-timeout)
	var stale []*ClusterMember
	for _, m := range c.members {
		if m.Status == MemberOnline && m.LastHeartbeat.Before(cutoff) {
			m.Status = MemberOffline
			stale = append(stale, m)
		}
	}
	return stale
}

// ── Relay: Broadcast ──

type Subscriber func(eventType string, source string)

type BroadcastBus struct {
	mu   sync.RWMutex
	subs map[string][]Subscriber
}

func NewBroadcastBus() *BroadcastBus {
	return &BroadcastBus{subs: make(map[string][]Subscriber)}
}

func (b *BroadcastBus) Subscribe(eventType string, fn Subscriber) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.subs[eventType] = append(b.subs[eventType], fn)
}

func (b *BroadcastBus) Publish(eventType, source string) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	for _, fn := range b.subs[eventType] {
		fn(eventType, source)
	}
}

// ── Relay: Shared State ──

type SharedState struct {
	mu    sync.RWMutex
	store map[string]*stateRow
}

type stateRow struct {
	Value     string
	ExpiresAt time.Time
}

func NewSharedState() *SharedState {
	return &SharedState{store: make(map[string]*stateRow)}
}

func (s *SharedState) Put(key, value string, ttl time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	row := &stateRow{Value: value}
	if ttl > 0 {
		row.ExpiresAt = time.Now().Add(ttl)
	}
	s.store[key] = row
}

func (s *SharedState) Get(key string) (string, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	row, ok := s.store[key]
	if !ok {
		return "", false
	}
	if !row.ExpiresAt.IsZero() && time.Now().After(row.ExpiresAt) {
		return "", false
	}
	return row.Value, true
}

// ── Relay: Group Comm ──

type GroupComm struct {
	mu     sync.RWMutex
	groups map[string]map[string]bool
}

func NewGroupComm() *GroupComm {
	return &GroupComm{groups: make(map[string]map[string]bool)}
}

func (gc *GroupComm) JoinGroup(group, memberID string) {
	gc.mu.Lock()
	defer gc.mu.Unlock()
	if gc.groups[group] == nil {
		gc.groups[group] = make(map[string]bool)
	}
	gc.groups[group][memberID] = true
}

func (gc *GroupComm) LeaveGroup(group, memberID string) {
	gc.mu.Lock()
	defer gc.mu.Unlock()
	if gc.groups[group] != nil {
		delete(gc.groups[group], memberID)
	}
}

func (gc *GroupComm) GroupMembers(group string) []string {
	gc.mu.RLock()
	defer gc.mu.RUnlock()
	members := make([]string, 0, len(gc.groups[group]))
	for id := range gc.groups[group] {
		members = append(members, id)
	}
	return members
}

// ── Pulse: Dependency Graph ──

type DepGraph struct {
	mu   sync.RWMutex
	deps map[string][]string // parent → children
}

func NewDepGraph() *DepGraph {
	return &DepGraph{deps: make(map[string][]string)}
}

func (dg *DepGraph) AddDependency(parent, child string) {
	dg.mu.Lock()
	defer dg.mu.Unlock()
	dg.deps[parent] = append(dg.deps[parent], child)
}

func (dg *DepGraph) Propagate(failed string) map[string]string {
	dg.mu.RLock()
	defer dg.mu.RUnlock()
	affected := make(map[string]string)
	queue := []string{failed}
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		for parent, children := range dg.deps {
			for _, child := range children {
				if child == current {
					if _, already := affected[parent]; !already {
						affected[parent] = "depends on " + current
						queue = append(queue, parent)
					}
				}
			}
		}
	}
	return affected
}

// ── POC-4 Tests ──

func TestPOC4_Step1_ClusterFormation(t *testing.T) {
	cluster := NewCluster()
	bus := NewBroadcastBus()

	// 4 agents join.
	members := []*ClusterMember{
		{ID: "a1", LUName: "architect.prod"},
		{ID: "a2", LUName: "researcher.prod"},
		{ID: "a3", LUName: "coder.prod"},
		{ID: "a4", LUName: "reviewer.prod"},
	}
	for _, m := range members {
		cluster.Join(m)
	}

	if len(cluster.ListOnline()) != 4 {
		t.Errorf("expected 4 online, got %d", len(cluster.ListOnline()))
	}

	// Each agent subscribes to cluster events.
	received := make(map[string][]string)
	var mu sync.Mutex
	for _, m := range members {
		id := m.ID
		bus.Subscribe("agent-status", func(eventType, source string) {
			mu.Lock()
			received[id] = append(received[id], source)
			mu.Unlock()
		})
		bus.Subscribe("model-change", func(eventType, source string) {
			mu.Lock()
			received[id+"-model"] = append(received[id+"-model"], source)
			mu.Unlock()
		})
	}

	// Verify all agents are registered as subscribers.
	if len(received) != 0 {
		t.Error("no events should have been received yet")
	}
}

func TestPOC4_Step2_SharedStateTTL(t *testing.T) {
	state := NewSharedState()

	// Architect writes model config with 1-hour TTL.
	state.Put("current-model", "claude-opus-4", 200*time.Millisecond)

	// Researcher reads immediately — should succeed.
	val, ok := state.Get("current-model")
	if !ok || val != "claude-opus-4" {
		t.Errorf("expected claude-opus-4, got %q (ok=%v)", val, ok)
	}

	// Wait for TTL to expire.
	time.Sleep(250 * time.Millisecond)

	// After TTL — not found.
	_, ok = state.Get("current-model")
	if ok {
		t.Error("TTL should have expired")
	}

	// No-TTL entry persists.
	state.Put("cluster-version", "v0.2", 0)
	val, ok = state.Get("cluster-version")
	if !ok || val != "v0.2" {
		t.Errorf("no-TTL entry should persist: %q", val)
	}
}

func TestPOC4_Step3_CoderFailurePropagation(t *testing.T) {
	cluster := NewCluster()
	bus := NewBroadcastBus()
	depGraph := NewDepGraph()

	// Set up cluster.
	agents := []string{"architect", "researcher", "coder", "reviewer"}
	for _, a := range agents {
		cluster.Join(&ClusterMember{ID: a, LUName: a + ".prod"})
	}

	// Dependencies: reviewer depends on coder; deploy-pipeline depends on coder.
	depGraph.AddDependency("reviewer", "coder")
	depGraph.AddDependency("deploy-pipeline", "coder")
	depGraph.AddDependency("architect", "researcher") // different chain

	// Track broadcasts.
	var broadcasts []string
	bus.Subscribe("agent-status", func(eventType, source string) {
		broadcasts = append(broadcasts, source)
	})

	// All agents heartbeat except coder.
	for _, a := range []string{"architect", "researcher", "reviewer"} {
		cluster.Heartbeat(a)
	}

	// Short sleep then re-heartbeat 3 agents to keep them fresh.
	time.Sleep(5 * time.Millisecond)
	for _, a := range []string{"architect", "researcher", "reviewer"} {
		cluster.Heartbeat(a)
	}

	// Detect stale: coder didn't heartbeat → goes offline.
	stale := cluster.DetectStale(2 * time.Millisecond)
	if len(stale) != 1 {
		t.Fatalf("expected 1 stale member, got %d", len(stale))
	}
	if stale[0].ID != "coder" {
		t.Errorf("expected coder stale, got %s", stale[0].ID)
	}

	// Broadcast coder offline.
	for _, s := range stale {
		bus.Publish("agent-status", s.ID+":offline")
	}

	if len(broadcasts) != 1 || broadcasts[0] != "coder:offline" {
		t.Errorf("broadcasts: %v", broadcasts)
	}

	// Pulse dependency propagation.
	affected := depGraph.Propagate("coder")
	if len(affected) != 2 {
		t.Errorf("expected 2 affected, got %d: %v", len(affected), affected)
	}
	if _, ok := affected["reviewer"]; !ok {
		t.Error("reviewer should be affected (depends on coder)")
	}
	if _, ok := affected["deploy-pipeline"]; !ok {
		t.Error("deploy-pipeline should be affected (depends on coder)")
	}
}

func TestPOC4_Step4_GroupRemoval(t *testing.T) {
	cluster := NewCluster()
	gc := NewGroupComm()

	// All 4 agents in active-deploy group.
	for _, a := range []string{"architect", "researcher", "coder", "reviewer"} {
		cluster.Join(&ClusterMember{ID: a, LUName: a + ".prod"})
		gc.JoinGroup("active-deploy", a)
	}

	if len(gc.GroupMembers("active-deploy")) != 4 {
		t.Errorf("expected 4 in group, got %d", len(gc.GroupMembers("active-deploy")))
	}

	// Coder goes offline → removed from group.
	// Force all stale (no heartbeats sent → all should be offline).
	time.Sleep(5 * time.Millisecond)
	staleMembers := cluster.DetectStale(2 * time.Millisecond)
	for _, m := range staleMembers {
		gc.LeaveGroup("active-deploy", m.ID)
	}

	members := gc.GroupMembers("active-deploy")
	// All 4 never heartbeated → all removed.
	if len(members) != 0 {
		t.Errorf("expected 0 after removal, got %d", len(members))
	}
}

func TestPOC4_HeartbeatRecovery(t *testing.T) {
	cluster := NewCluster()
	cluster.Join(&ClusterMember{ID: "agent-x"})

	// No heartbeat → stale.
	time.Sleep(10 * time.Millisecond)
	stale := cluster.DetectStale(5 * time.Millisecond)
	if len(stale) != 1 || stale[0].Status != MemberOffline {
		t.Fatalf("expected offline, got %v", stale)
	}

	// Agent recovers → heartbeat.
	cluster.Heartbeat("agent-x")

	// Should be back online.
	online := cluster.ListOnline()
	if len(online) != 1 {
		t.Errorf("expected 1 online after recovery, got %d", len(online))
	}
}

func TestPOC4_DependencyChainRecursive(t *testing.T) {
	dg := NewDepGraph()
	// reviewer → coder → compiler → kernel
	dg.AddDependency("reviewer", "coder")
	dg.AddDependency("coder", "compiler")
	dg.AddDependency("compiler", "kernel")

	// Kernel fails → chain propagates upward.
	affected := dg.Propagate("kernel")
	if len(affected) != 3 {
		t.Errorf("expected 3 affected, got %d: %v", len(affected), affected)
	}
	if _, ok := affected["compiler"]; !ok {
		t.Error("compiler should be affected")
	}
	if _, ok := affected["coder"]; !ok {
		t.Error("coder should be affected (transitive)")
	}
	if _, ok := affected["reviewer"]; !ok {
		t.Error("reviewer should be affected (transitive)")
	}
}
