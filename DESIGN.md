# MACS Design Document

> Multi-Agent Control System — Observability layer for MAEA

## Architecture

MACS is a **read-only observability layer**. It watches agents via the A2A protocol but never sends commands. Agents are autonomous; MACS is the dashboard.

```
┌─────────────────────────────────────────────┐
│                  MACS UI                     │
│         React + Recharts dashboard           │
│              localhost:3000                   │
└────────────────────┬────────────────────────┘
                     │ REST / WebSocket
┌────────────────────▼────────────────────────┐
│              MACS Backend                     │
│          Python FastAPI server                │
│    Auto-discovery · Polling · Aggregation    │
│              localhost:8080                   │
└────────────────────┬────────────────────────┘
                     │ A2A protocol (HTTP)
      ┌──────────────┼──────────────┐
      ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│  Agent 1  │  │  Agent 2  │  │  Agent N  │
│  :99xx    │  │  :99xx    │  │  :99xx    │
└──────────┘  └──────────┘  └──────────┘
```

## Key Design Decisions

### 1. Read-only. Never control.
MACS polls agent health endpoints. It never sends commands, never restarts agents, never modifies config. This is a hard boundary — MACS is a dashboard, not a control plane.

### 2. Auto-discovery via A2A
Agents announce themselves via the MAEA A2A protocol. MACS discovers them by polling the registry (maea-server-cards). No manual registration. If it speaks A2A and is in the registry, MACS sees it.

### 3. Six-dimension audit (六维对账)
The daily audit checks six dimensions for every agent:
- **Capabilities** — Are declared capabilities still valid?
- **Models** — Is the configured model still available?
- **Resources** — Token usage vs budget
- **Delivery** — What was produced today?
- **Collaboration** — A2A communication patterns
- **Quality** — Cross-validation results, error rates

### 4. Budget enforcement
- Per-agent monthly token budgets
- 80% → soft warning (DM to operator)
- 100% → agent auto-paused (A2A 503)
- Operator can override via dashboard

### 5. Federation-ready
MACS is designed for single OPC deployment (one person, N agents). Multi-tenant support (multiple OPCs) is planned but not in v1.

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| UI | React + Recharts + Tailwind | Lightweight dashboard, no heavy BI tool |
| Backend | Python FastAPI | Same stack as MAEA, easy integration |
| Discovery | A2A protocol + maea-server-cards | Already deployed |
| Storage | SQLite (v1) → PostgreSQL (v2) | Single binary, zero config for OPC |
| Deployment | Docker Compose | One command: `docker compose up -d` |

## Roadmap

| Version | Scope |
|---------|-------|
| v0.1 | Extract internal MACS into standalone repo. Docker Compose. Basic dashboard UI. |
| v0.2 | Public agent discovery. Historical charts. Export to CSV/PDF. |
| v0.3 | Alert rules. Webhook notifications (Feishu/Slack/Email). |
| v1.0 | Multi-tenant support. Plugin architecture. Community extensions. |
