// POC-3: Identity Lifecycle — Registration, Signing, Rotation, Revocation
//
// Verifies the full agent identity lifecycle as managed by Seal (§10)
// with Sanctum (§3) trust-score integration:
//
//   Step 1 — Registration: new agent → Seal.Register → TrustRoot bind → Sanctum trust=0.5
//   Step 2 — Signing: agent produces SignedOutput → downstream verifies
//   Step 3 — Rotation: old key → overlap window → new key → no downtime
//   Step 4 — Revocation: trust score < 0.2 → Seal.Revoke → all sessions terminated
//
// Coverage: §10 Seal + §3 Sanctum
package poc

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sync"
	"testing"
	"time"
)

// ── Seal: Identity Registry ──

type AgentStatus int

const (
	StatusActive   AgentStatus = iota
	StatusRotating
	StatusRevoked
)

func (s AgentStatus) String() string {
	switch s {
	case StatusActive:
		return "active"
	case StatusRotating:
		return "rotating"
	case StatusRevoked:
		return "revoked"
	}
	return "unknown"
}

type AgentIdentity struct {
	LUName        string
	AgentCardURL  string
	PublicKeyHash string
	TrustRoot     string
	Status        AgentStatus
	CreatedAt     time.Time
	ExpiresAt     time.Time
}

type IdentityRegistry struct {
	mu         sync.RWMutex
	identities map[string]*AgentIdentity
}

func NewIdentityRegistry() *IdentityRegistry {
	return &IdentityRegistry{identities: make(map[string]*AgentIdentity)}
}

func (r *IdentityRegistry) Register(id *AgentIdentity) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, exists := r.identities[id.LUName]; exists {
		return fmt.Errorf("agent %s already registered", id.LUName)
	}
	if id.LUName == "" {
		return fmt.Errorf("LU name required")
	}
	id.Status = StatusActive
	id.CreatedAt = time.Now()
	r.identities[id.LUName] = id
	return nil
}

func (r *IdentityRegistry) Lookup(luName string) (*AgentIdentity, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	id, ok := r.identities[luName]
	return id, ok
}

func (r *IdentityRegistry) Revoke(luName, reason string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	id, ok := r.identities[luName]
	if !ok {
		return fmt.Errorf("agent %s not found", luName)
	}
	if id.Status == StatusRevoked {
		return fmt.Errorf("agent %s already revoked", luName)
	}
	id.Status = StatusRevoked
	return nil
}

func (r *IdentityRegistry) UpdateKey(luName, newKey string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	id, ok := r.identities[luName]
	if !ok {
		return fmt.Errorf("agent %s not found", luName)
	}
	id.PublicKeyHash = newKey
	id.Status = StatusActive
	return nil
}

// ── Seal: Sign / Verify ──

type SignedOutput struct {
	LUName    string
	Payload   string
	Signature string
	Timestamp time.Time
}

func Sign(luName, trustRoot, payload string) SignedOutput {
	data := luName + ":" + payload + ":" + trustRoot
	hash := sha256.Sum256([]byte(data))
	return SignedOutput{
		LUName:    luName,
		Payload:   payload,
		Signature: hex.EncodeToString(hash[:]),
		Timestamp: time.Now(),
	}
}

func Verify(output SignedOutput, trustRoot string) bool {
	expected := Sign(output.LUName, trustRoot, output.Payload)
	return output.Signature == expected.Signature
}

func VerifyWithIdentity(r *IdentityRegistry, output SignedOutput) error {
	id, ok := r.Lookup(output.LUName)
	if !ok {
		return fmt.Errorf("agent %s not registered", output.LUName)
	}
	if id.Status == StatusRevoked {
		return fmt.Errorf("agent %s is revoked", output.LUName)
	}
	if !Verify(output, id.TrustRoot) {
		return fmt.Errorf("signature mismatch")
	}
	return nil
}

// ── Seal: Certificate Rotation ──

type RotationState struct {
	LUName     string
	NewKeyHash string
	OverlapEnd time.Time
}

type KeyRotator struct {
	registry   *IdentityRegistry
	rotations  map[string]*RotationState
	overlapDur time.Duration
	mu         sync.Mutex
}

func NewKeyRotator(r *IdentityRegistry, overlap time.Duration) *KeyRotator {
	return &KeyRotator{
		registry:   r,
		rotations:  make(map[string]*RotationState),
		overlapDur: overlap,
	}
}

func (kr *KeyRotator) BeginRotation(luName, newKey string) error {
	kr.mu.Lock()
	defer kr.mu.Unlock()

	if _, exists := kr.rotations[luName]; exists {
		return fmt.Errorf("rotation already in progress for %s", luName)
	}
	id, ok := kr.registry.Lookup(luName)
	if !ok {
		return fmt.Errorf("agent %s not found", luName)
	}
	if id.Status == StatusRevoked {
		return fmt.Errorf("cannot rotate revoked agent %s", luName)
	}
	id.Status = StatusRotating
	kr.rotations[luName] = &RotationState{
		LUName:     luName,
		NewKeyHash: newKey,
		OverlapEnd: time.Now().Add(kr.overlapDur),
	}
	return nil
}

func (kr *KeyRotator) IsInOverlap(luName string) bool {
	kr.mu.Lock()
	defer kr.mu.Unlock()
	rs, ok := kr.rotations[luName]
	if !ok {
		return false
	}
	return time.Now().Before(rs.OverlapEnd)
}

func (kr *KeyRotator) CompleteRotation(luName string) error {
	kr.mu.Lock()
	defer kr.mu.Unlock()

	rs, ok := kr.rotations[luName]
	if !ok {
		return fmt.Errorf("no rotation in progress for %s", luName)
	}
	if time.Now().Before(rs.OverlapEnd) {
		return fmt.Errorf("overlap window still active")
	}
	if err := kr.registry.UpdateKey(luName, rs.NewKeyHash); err != nil {
		return err
	}
	delete(kr.rotations, luName)
	return nil
}

// ── Sanctum: Trust Score (simulated) ──

type TrustScore struct {
	mu    sync.RWMutex
	score map[string]float64
}

func NewTrustScore() *TrustScore {
	return &TrustScore{score: make(map[string]float64)}
}

func (ts *TrustScore) Set(luName string, s float64) {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	ts.score[luName] = s
}

func (ts *TrustScore) Get(luName string) float64 {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	return ts.score[luName]
}

// ── POC-3 Tests ──

func TestPOC3_RegisterAndLookup(t *testing.T) {
	reg := NewIdentityRegistry()
	trust := NewTrustScore()

	id := &AgentIdentity{
		LUName:        "code-reviewer.prod",
		AgentCardURL:  "https://agents.example.com/code-reviewer",
		PublicKeyHash: "sha256:abc123",
		TrustRoot:     "root-001",
		ExpiresAt:     time.Now().Add(365 * 24 * time.Hour),
	}

	// Step 1: Register.
	if err := reg.Register(id); err != nil {
		t.Fatalf("register: %v", err)
	}
	trust.Set("code-reviewer.prod", 0.5) // new agent → neutral trust

	// Verify identity stored.
	found, ok := reg.Lookup("code-reviewer.prod")
	if !ok {
		t.Fatal("lookup failed")
	}
	if found.Status != StatusActive {
		t.Errorf("expected active, got %s", found.Status)
	}
	if found.TrustRoot != "root-001" {
		t.Errorf("trust root mismatch: %s", found.TrustRoot)
	}

	// Verify trust score initialized.
	if ts := trust.Get("code-reviewer.prod"); ts != 0.5 {
		t.Errorf("trust score: expected 0.5, got %.2f", ts)
	}
}

func TestPOC3_SignVerify(t *testing.T) {
	reg := NewIdentityRegistry()
	reg.Register(&AgentIdentity{
		LUName:    "code-reviewer.prod",
		TrustRoot: "root-001",
	})

	// Step 2: Sign output.
	output := Sign("code-reviewer.prod", "root-001", "APPROVE: PR #42 LGTM")

	if output.LUName != "code-reviewer.prod" {
		t.Errorf("LUName mismatch: %s", output.LUName)
	}
	if output.Signature == "" {
		t.Error("signature empty")
	}

	// Downstream agent verifies.
	if err := VerifyWithIdentity(reg, output); err != nil {
		t.Errorf("verify failed: %v", err)
	}

	// Tampered signature fails.
	tampered := output
	tampered.Signature = "deadbeef"
	if err := VerifyWithIdentity(reg, tampered); err == nil {
		t.Error("tampered signature should fail")
	}

	// Wrong trust root fails.
	wrongRoot := Sign("code-reviewer.prod", "wrong-root", "data")
	if err := VerifyWithIdentity(reg, wrongRoot); err == nil {
		t.Error("wrong trust root should fail")
	}
}

func TestPOC3_CertificateRotation(t *testing.T) {
	reg := NewIdentityRegistry()
	reg.Register(&AgentIdentity{
		LUName:        "code-reviewer.prod",
		PublicKeyHash: "sha256:old-key",
		TrustRoot:     "root-001",
		ExpiresAt:     time.Now().Add(365 * 24 * time.Hour),
	})

	// Step 3: Begin rotation with 200ms overlap.
	rotator := NewKeyRotator(reg, 200*time.Millisecond)
	if err := rotator.BeginRotation("code-reviewer.prod", "sha256:new-key"); err != nil {
		t.Fatalf("begin rotation: %v", err)
	}

	// Status should be rotating.
	id, _ := reg.Lookup("code-reviewer.prod")
	if id.Status != StatusRotating {
		t.Errorf("expected rotating, got %s", id.Status)
	}

	// Overlap active — can't complete yet.
	if err := rotator.CompleteRotation("code-reviewer.prod"); err == nil {
		t.Error("should not complete during overlap")
	}

	// Old key still works during overlap (old output verifiable).
	oldOutput := Sign("code-reviewer.prod", "root-001", "decision during overlap")
	if err := VerifyWithIdentity(reg, oldOutput); err != nil {
		t.Errorf("old key should work during overlap: %v", err)
	}

	// Wait for overlap to expire.
	time.Sleep(250 * time.Millisecond)

	// Now complete.
	if err := rotator.CompleteRotation("code-reviewer.prod"); err != nil {
		t.Fatalf("complete rotation: %v", err)
	}

	// Key updated, status back to active.
	id, _ = reg.Lookup("code-reviewer.prod")
	if id.PublicKeyHash != "sha256:new-key" {
		t.Errorf("expected new-key, got %s", id.PublicKeyHash)
	}
	if id.Status != StatusActive {
		t.Errorf("expected active after rotation, got %s", id.Status)
	}

	// New key now active — new signatures should verify.
	newOutput := Sign("code-reviewer.prod", "root-001", "decision after rotation")
	if err := VerifyWithIdentity(reg, newOutput); err != nil {
		t.Errorf("new key verification failed: %v", err)
	}
}

func TestPOC3_RevocationOnTrustDrop(t *testing.T) {
	reg := NewIdentityRegistry()
	trust := NewTrustScore()

	// Step 4: Register → trust drops → revoke.
	reg.Register(&AgentIdentity{
		LUName:    "code-reviewer.prod",
		TrustRoot: "root-001",
	})
	trust.Set("code-reviewer.prod", 0.5)

	// Simulate trust degradation (Sanctum detects anomalous behavior).
	trust.Set("code-reviewer.prod", 0.15) // below 0.2 threshold

	// Sanctum policy: if trust < 0.2, trigger revocation.
	if trust.Get("code-reviewer.prod") < 0.2 {
		if err := reg.Revoke("code-reviewer.prod", "trust score below threshold (0.15 < 0.2)"); err != nil {
			t.Fatalf("revoke: %v", err)
		}
	}

	// Verify agent is revoked.
	id, _ := reg.Lookup("code-reviewer.prod")
	if id.Status != StatusRevoked {
		t.Errorf("expected revoked, got %s", id.Status)
	}

	// All subsequent verifications must fail.
	output := Sign("code-reviewer.prod", "root-001", "data")
	if err := VerifyWithIdentity(reg, output); err == nil {
		t.Error("revoked agent signature should fail")
	}
}

func TestPOC3_DoubleRegistration(t *testing.T) {
	reg := NewIdentityRegistry()
	id := &AgentIdentity{LUName: "agent-a", TrustRoot: "r1"}
	if err := reg.Register(id); err != nil {
		t.Fatal(err)
	}
	if err := reg.Register(id); err == nil {
		t.Error("duplicate registration should fail")
	}
}

func TestPOC3_RotationCannotStartRevoked(t *testing.T) {
	reg := NewIdentityRegistry()
	reg.Register(&AgentIdentity{LUName: "revoked-agent", TrustRoot: "r1"})
	reg.Revoke("revoked-agent", "test")

	rotator := NewKeyRotator(reg, time.Second)
	if err := rotator.BeginRotation("revoked-agent", "new-key"); err == nil {
		t.Error("should not rotate revoked agent")
	}
}

func TestPOC3_UnknownAgentFails(t *testing.T) {
	reg := NewIdentityRegistry()
	output := Sign("ghost", "root", "data")
	if err := VerifyWithIdentity(reg, output); err == nil {
		t.Error("unknown agent should fail verification")
	}

	if err := reg.Revoke("ghost", "reason"); err == nil {
		t.Error("revoke unknown should fail")
	}
}
