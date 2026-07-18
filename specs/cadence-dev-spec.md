# MACS Cadence v0.1 — Development Spec

## Overview

Implement `macs-cadence-go` — MACS §6 batch processing engine. Single Go package `pkg/cadence/` with zero external dependencies (only stdlib).

## Package Structure

```
macs-cadence-go/
├── go.mod
├── go.sum
├── LICENSE
├── README.md
└── pkg/
    └── cadence/
        ├── doc.go           // package documentation
        ├── types.go         // Job, JobStatus, JobPriority, JobOutput
        ├── queue.go         // JobQueue — priority heap
        ├── initiator.go     // InitiatorPool — goroutine workers
        ├── output.go        // JobOutput store
        ├── chain.go         // JobChainer — DAG successor trigger
        └── cadence_test.go  // all tests
```

## Component Specs

### types.go

```go
type JobPriority int
const (
    PriorityCritical    JobPriority = 1  // Regulator importance 1
    PriorityHigh        JobPriority = 2
    PriorityMedium      JobPriority = 3
    PriorityLow         JobPriority = 4  // Discretionary
)

type JobStatus string
const (
    StatusQueued    JobStatus = "QUEUED"
    StatusRunning   JobStatus = "RUNNING"
    StatusCompleted JobStatus = "COMPLETED"
    StatusFailed    JobStatus = "FAILED"
    StatusCancelled JobStatus = "CANCELLED"
)

type Job struct {
    ID        string
    LUName    string      // Agent Logical Unit name
    Priority  JobPriority
    Command   string      // opaque string — Cadence doesn't interpret
    Status    JobStatus
    Created   time.Time
    Started   time.Time
    Completed time.Time
    Output    string
    NextJobs  []string    // job chaining: IDs to trigger on completion
}

type JobOutput struct {
    JobID  string
    Status JobStatus
    Output string
    Error  string
}
```

### queue.go — JobQueue

Priority heap (container/heap). Jobs ordered by:
1. Priority (1=critical first, 4=low last)
2. Created timestamp (FIFO within same priority)

API:
```
func NewJobQueue(maxDepth int) *JobQueue
func (q *JobQueue) Submit(job Job) error   // ErrQueueFull if at maxDepth
func (q *JobQueue) Dequeue() (Job, bool)   // pop highest priority
func (q *JobQueue) Peek() (Job, bool)      // inspect without dequeue
func (q *JobQueue) Cancel(jobID string) bool
func (q *JobQueue) Len() int
func (q *JobQueue) List() []Job            // snapshot, sorted
func (q *JobQueue) Get(jobID string) (Job, bool)
```

### initiator.go — InitiatorPool

N goroutines, each polling JobQueue + Checkpoint.

```
func NewInitiatorPool(n int, queue *JobQueue, cp Checkpointer) *InitiatorPool
func (p *InitiatorPool) Start()
func (p *InitiatorPool) Stop()
func (p *InitiatorPool) Running() int
```

Checkpointer interface (injected, not imported):
```go
type Checkpointer interface {
    Register(jobID string)
    Claim(jobID, owner string) bool
    Complete(jobID string)
    Release(jobID string)
}
```

Initiator loop:
1. `queue.Dequeue()` → get highest-priority job
2. `cp.Claim(job.ID, initiatorID)` → atomic claim
3. If claim fails → skip (another initiator got it)
4. Set status RUNNING, invoke executor callback
5. On completion → `cp.Complete(job.ID)`, store output, trigger chain
6. On failure → `cp.Release(job.ID)`, mark FAILED

Executor callback (injected):
```go
type Executor func(job Job) (output string, err error)
```

### output.go — JobOutput store

Thread-safe map of completed/failed jobs.

```
func NewJobOutput() *JobOutput
func (o *JobOutput) Store(jobID string, output JobOutput)
func (o *JobOutput) Get(jobID string) (JobOutput, bool)
func (o *JobOutput) List(status JobStatus) []JobOutput
```

### chain.go — JobChainer

Trigger successor jobs on completion.

```
func (c *Cadence) TriggerChain(completedJobID string) error
```

On job completion or cancellation:
1. Look up job's `NextJobs` list
2. For each successor ID, check if it exists in queue
3. If status is QUEUED, keep it (normal path). If chained from cancelled, optionally cascade-cancel.

## Configuration

Parsed from PARMLIB CADENCE.yaml (loaded by caller, passed as struct):
```go
type CadenceConfig struct {
    Initiators         int
    MaxQueueDepth      int
    DispatchIntervalMs int
}
```

## Error Types

```go
var (
    ErrQueueFull     = errors.New("cadence: job queue full")
    ErrJobNotFound   = errors.New("cadence: job not found")
    ErrJobNotRunning = errors.New("cadence: job not in running state")
)
```

## Integration Contract

Cadence v0.1 uses these integration points (from kernel/shared):
- `Checkpointer` interface — atomic claim/complete/release
- `Executor` callback — injected, not imported
- `Registry` — optional; if nil, Cadence operates without agent context

## Test Plan

| # | Test | Coverage |
|:--:|------|------|
| T01 | Submit single job → dequeued in priority order | queue.go |
| T02 | FIFO ordering within same priority | queue.go |
| T03 | Queue full rejects submission | queue.go |
| T04 | Cancel mid-queue job | queue.go |
| T05 | Peek doesn't remove | queue.go |
| T06 | List returns sorted snapshot | queue.go |
| T07 | Get finds by ID | queue.go |
| T08 | Initiator pool starts N goroutines | initiator.go |
| T09 | Job completes → output stored | initiator.go |
| T10 | Job fails → status FAILED | initiator.go |
| T11 | Claim conflict — another initiator took it | initiator.go |
| T12 | Stop drains running initiators | initiator.go |
| T13 | Output store → Get returns stored result | output.go |
| T14 | Output store → List filters by status | output.go |
| T15 | Chain triggers successor on completion | chain.go |
| T16 | Chain cascade-cancels on predecessor cancel | chain.go |
| T17 | Empty queue + empty output → no panic | edge cases |
| T18 | Concurrent submit + dequeue — no data race | race detector |
