# MACS Cadence v0.1 — Acceptance Tests

## AT-1: Queue Priority Ordering
- **GIVEN** jobs with priorities [3, 1, 4, 2]
- **WHEN** all submitted and dequeued in order
- **THEN** dequeue order is [1, 2, 3, 4] (critical first)

## AT-2: Queue FIFO Tie-Breaking
- **GIVEN** 3 jobs all Priority=2, submitted as A→B→C
- **WHEN** dequeued
- **THEN** order is A, B, C (FIFO within same priority)

## AT-3: Queue Full Rejection
- **GIVEN** queue with maxDepth=3, filled with 3 jobs
- **WHEN** 4th job submitted
- **THEN** returns ErrQueueFull

## AT-4: Queue Cancel
- **GIVEN** job in queue, status QUEUED
- **WHEN** Cancel(jobID)
- **THEN** status → CANCELLED, not dequeued by initiator

## AT-5: Queue Peek
- **GIVEN** queue with 3 jobs
- **WHEN** Peek() called
- **THEN** returns highest-priority job, queue length unchanged

## AT-6: Initiator Pool Start
- **GIVEN** pool with n=4
- **WHEN** Start()
- **THEN** Running() == 4

## AT-7: Job Completes
- **GIVEN** job in queue, executor returns (output, nil)
- **WHEN** initiator processes it
- **THEN** job.Status == COMPLETED, output stored, output.Get(jobID) returns result

## AT-8: Job Fails
- **GIVEN** job in queue, executor returns ("", error)
- **WHEN** initiator processes it
- **THEN** job.Status == FAILED, error message in output.Error

## AT-9: Claim Conflict
- **GIVEN** 1 job in queue, 2 initiators poll simultaneously
- **WHEN** both attempt Claim()
- **THEN** only one gets true; the other skips and queue becomes empty (no duplicate execution)

## AT-10: Stop Drains Initiators
- **GIVEN** pool with 3 running initiators
- **WHEN** Stop() called
- **THEN** Running() → 0, all goroutines exited

## AT-11: Output Store List by Status
- **GIVEN** 2 COMPLETED and 1 FAILED outputs stored
- **WHEN** List(StatusCompleted)
- **THEN** returns 2 entries only

## AT-12: Chain Trigger on Success
- **GIVEN** job A with NextJobs=[B], B in queue as QUEUED
- **WHEN** A completes
- **THEN** B remains in queue (normal path — initiator picks it up)

## AT-13: Chain Cancel on Predecessor Cancel
- **GIVEN** job A with NextJobs=[B], B in queue as QUEUED
- **WHEN** A cancelled
- **THEN** B → CANCELLED (cascade)

## AT-14: Empty Queue Graceful
- **GIVEN** empty queue, initiator running
- **WHEN** Dequeue() returns false
- **THEN** initiator sleeps dispatch_interval and retries (no panic)

## AT-15: Concurrent Safety
- **GIVEN** queue with 100 jobs, 4 initiators processing
- **WHEN** go test -race
- **THEN** no data races detected

## AT-16: Job ID Uniqueness
- **GIVEN** job submitted with duplicate ID
- **WHEN** already in queue
- **THEN** Submit() returns error

## AT-17: Get Job by ID from Queue
- **GIVEN** job in queue (not yet dequeued)
- **WHEN** queue.Get(jobID)
- **THEN** returns job with status QUEUED

## AT-18: List All Jobs
- **GIVEN** 5 jobs in various states
- **WHEN** queue.List()
- **THEN** returns all 5 sorted by priority+time

## AT-19: Config Validation
- **GIVEN** CadenceConfig with initiators=0
- **WHEN** NewInitiatorPool(0, ...)
- **THEN** defaults to 1 (minimum 1 initiator)

## AT-20: Max Queue Depth Zero
- **GIVEN** JobQueue with maxDepth=0
- **WHEN** job submitted
- **THEN** returns ErrQueueFull (unbounded queues not allowed)
