# JES Gate — Batch Admission Control

> MACS §6 JES: WLM-aware cron gate. Blocks low-importance batch jobs when
> the token budget is tight. High-importance jobs always pass.

## Quick Start

```bash
# Wrap any cron command with an importance level
python3 ~/.hermes/scripts/jes-gate --importance 2 --command "hermes cron run bank-procurement"

# importance=1: only blocked at black (critical — never starved)
# importance=2: blocked at red or black
# importance=3: blocked at yellow, red, or black (best-effort batch)
```

## How It Works

1. The `wlm-token` hook writes `~/.hermes/wlm_signal.txt` on every agent start
2. Before a cron job fires, `jes-gate` reads the signal
3. If the worst signal level across all agent classes is at or above the
   job's block threshold, the gate exits with code 1 (blocked)
4. If admitted, the gate passes control to the cron command

```
Cron trigger → jes-gate (read WLM signal) → admitted? → execute
                                               │
                                               └ blocked → log + exit 1
```

## Hermes Cron Integration

```bash
# In Hermes cron job config, wrap the command with jes-gate:
hermes cron create \
  --name "bank-procurement-daily" \
  --schedule "0 9 * * *" \
  --command "python3 ~/.hermes/scripts/jes-gate --importance 2 --command 'hermes cron run bank-procurement-collect'"
```

When WLM hits red:
- `bank-procurement-daily` (importance=2) → **blocked**, it can wait
- `architecture-health-check` (importance=1) → **still runs**, critical path

## Signal Format

`jes-gate` reads `~/.hermes/wlm_signal.txt`:

```
# WLM Token Budget — updated 2026-07-03T10:00:00Z
🟢 sg-architect           green  10,000/100,000 tokens (10%)
🟡 do-developer          yellow  45,000/100,000 tokens (45%)
🔴 do-ops                   red  85,000/100,000 tokens (85%)
```

The gate uses the **worst** signal across all classes. If ANY class is
at a blocking level, all batch jobs at that importance or lower are blocked.

## Non-Goals

- Job chaining (JCL COND: job A → triggers job B) — future
- Priority preemption within the same gate level — future
- Result delivery as structured Agent reports — currently raw stdout

## Design

`jes-gate` is a standalone Python script. No dependencies beyond stdlib.
No Hermes core changes. No pip install. It is the CICS SPOOL output queue
applied to cron — the batch scheduler decides admission; the kernel (WLM)
provides the signal.

---

> *MACS §6 JES · 2026-07-03*
