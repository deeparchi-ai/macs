# MACS — Your agents' mission control.

**Real-time health, budgets, and governance for multi-agent teams.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status: Active Development](https://img.shields.io/badge/status-active%20development-green)]()

**Quickstart** · [**Docs**](docs/) · [**GitHub**](https://github.com/deeparchi-ai/macs) · [**Website**](https://www.deeparchi.com.cn)

---

## Your agents are running. Do you know what they're doing?

You have 5, 10, 20 AI agents running your business. Some are coding, some are researching, some are talking to customers. 

**Who's actually working? Who's stuck? Who's burning tokens on nothing?**

MACS gives you a single pane of glass. Not a list of API logs. Not a terminal full of JSON. A dashboard that answers the only question that matters: **is my agent team healthy?**

<p align="center">
  <em>[Screenshot: MACS Dashboard — Coming soon]</em>
</p>

---

## What it shows you

| Panel | What you see | Why you care |
|-------|-------------|--------------|
| **Live心跳** | Which agents are online, which are down | Before you notice, the dashboard knows |
| **Token Spend** | Per-agent, per-day, per-project cost | No runaway bills. See who's expensive |
| **六维对账** | Capabilities · Models · Resources · Delivery · Collaboration · Quality | Catch drift before it becomes failure |
| **A2A 拓扑** | Agent-to-agent communication matrix | See who talks to who. Spot dead links |
| **预算告警** | Per-agent monthly caps. 80% soft, 100% hard | Budgets enforced, not suggested |
| **交付物审计** | What each agent produced today | "I ran 12 tasks" → show me the files |

---

## 30-second start

```bash
# Clone and run
git clone https://github.com/deeparchi-ai/macs.git
cd macs

# Start the dashboard
docker compose up -d

# Open http://localhost:3000
```

MACS auto-discovers agents on your network via the [MAEA A2A protocol](https://github.com/deeparchi-ai/MAEA-Framework). No agent registration needed — if it speaks A2A, MACS sees it.

---

## How it fits

```
                    ┌──────────────────────┐
                    │       MACS           │
                    │   (you are here)      │
                    │   监控 · 预算 · 治理    │
                    └──────────┬───────────┘
                               │ watches
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │ sg-architect │    │ cm-deepsight │    │ do-developer │
    │   :9900       │    │   :9920       │    │   :9912       │
    └──────────┘        └──────────┘        └──────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │ A2A protocol
                    ┌──────────▼───────────┐
                    │   MAEA Gateway       │
                    │   Agent registry     │
                    └──────────────────────┘
```

MACS is the observability layer of the [MAEA multi-agent framework](https://github.com/deeparchi-ai/MAEA-Framework). It watches, but doesn't control. Agents run independently — MACS is the dashboard, not the pilot.

> **If Paperclip is the org chart, MACS is the mission control.**

---

## Built for OPC

An OPC (One-Person Company) doesn't need Kubernetes monitoring. They need to know if their 5 agents are doing their jobs while they sleep.

| You don't need | You need |
|---------------|----------|
| Grafana + Prometheus + 5 dashboards | One screen that tells you everything |
| Per-service alert rules | "Something's wrong" — with a pointer to what |
| Infrastructure metrics | Agent-level health: is it working or stuck? |
| A DevOps team to maintain monitoring | `docker compose up -d` |

MACS is designed for the operator who is also the CEO, CTO, and COO. You have 3 minutes between meetings to check on your agents. Make them count.

---

## Current status

**Active development.** MACS powers the internal operations of [DeepArchi](https://www.deeparchi.com.cn), a 9-agent AI-native professional services firm. We're extracting the dashboard into a standalone open-source project.

| Component | Status |
|----------|--------|
| Agent auto-discovery (A2A) | ✅ Running internally |
| Live heartbeat monitoring | ✅ Running internally |
| Token spend tracking | ✅ Running internally |
| 六维对账 audit | ✅ Running internally |
| A2A topology matrix | ✅ Running internally |
| Docker Compose one-liner | 🚧 In progress |
| Public dashboard UI | 🚧 In progress |
| Multi-tenant (your agents + mine) | 📋 Planned |

---

## Open source

MIT licensed. Built by [DeepArchi](https://github.com/deeparchi-ai).

- **Why open source?** Agent infrastructure should be transparent. Your agents are running your business — you should see exactly how they're being monitored.
- **Why now?** Paperclip proved there's demand for agent orchestration. MACS proves there's demand for agent *observability*. Different layer, same problem: OPCs need to trust their agents.
- **Contributing:** We're extracting MACS from our internal deployment. Contributions welcome once the public build is ready — watch this repo.

---

**Quickstart** · [**Docs**](docs/) · [**GitHub**](https://github.com/deeparchi-ai/macs) · [**Website**](https://www.deeparchi.com.cn)

*Built for people who want to run companies, not babysit agents.*
