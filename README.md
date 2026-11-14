# AEG · Agent 执行治理

> 给 Agent 的执行装刹车与黑匣子：只能收紧的策略、跨 Agent 的证据树、会升级的交叉验证。
>
> AEG（Agent Execution Governance）治理的是 **Agent 做了什么**，不是模型是什么。一个 Agent 成立，一百个更成立。

| 部件 | 能力 | 一句话 |
|---|---|---|
| 刹车 | 单调策略 | 每次工具调用前判定，只能更严、不能放宽，默认只记录 |
| 黑匣子 | 跨 Agent 证据树 | 根 + 全部子 Agent，事实与判定按 callId 对齐 |
| 双人复核 | XVal | 不可逆操作上一张反对票就升级 |
| 适航审定 | 编制校验 | 环、孤点、深度、爆炸半径、预算合计 |

默认只记录不拦截：**先看清楚，再合口子。**

## AEG — Agent Execution Governance

> Brakes and a black box for agent execution: a policy that can only tighten, a cross-agent evidence tree, and review that escalates.
>
> AEG governs what an agent **does**, not what the model **is**. True for one agent; more so for a hundred.
>
> Observation only by default: **look first, then close the gate.**

## 术语

| 术语 | 含义 |
|---|---|
| **AEG**（Agent Execution Governance · Agent 执行治理） | 品类。治理的是 Agent 做了什么，不是模型是什么 |
| **执行面 · MACS** | 单次执行上的四件事：单调策略、跨 Agent 证据树、XVal 交叉验证、编制校验 → [macs](https://github.com/deeparchi-ai/macs) |
| **组织面 · MAEA** | 编制、章程、拓扑校验、交叉验证的组织侧规格 → [MAEA-Framework](https://github.com/deeparchi-ai/MAEA-Framework) |
| **单调策略** | 刹车：每次工具调用前判定，只能更严、不能放宽，默认只记录 |
| **跨 Agent 证据树** | 黑匣子：根 + 全部子 Agent，事实与判定按 callId 对齐，判决带当时策略哈希 |
| **XVal** | 双人复核：不可逆操作上一张反对票就升级，多数票不盖过 |
| **编制校验** | 适航审定：环、孤点、委派深度、爆炸半径、预算合计 |

Canonical specification: [MACS Governance Specification v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)

## 实现状态

三档：**可用** / **部分** / **POC**。逐子系统的实现仓库与测试数见 **[docs/subsystems.md](docs/subsystems.md)**。

| 状态 | 子系统 |
|:--:|---|
| **可用** | Loom（因果回滚 + 两阶段提交）· Chronicle（跨 Agent 证据与追踪）· XVal（交叉验证 + 供应商故障切换）· Curator（知识生命周期）· Nexus（协议准入）· Gauge（性能度量）· Seal（身份与签名）· Relay（集群状态）· Warden（崩溃恢复）· Pulse（自健康）· Console（操作控制台） |
| **部分** | Regulator（CPU 调度可用，Token 预算未完成）· Sanctum（v0.1 可用，trust scoring 未完成） |
| **POC** | Cadence（批调度准入闸门） |

## 规格

| Spec | Covers |
|------|--------|
| [security-model.md](specs/security-model.md) | Sanctum：工具剖面、参数域、程序路径限制 |
| [state-rollback.md](specs/state-rollback.md) | Loom：因果 DAG 回滚 + 两阶段提交 |
| [xval-dfsms-vtam.md](specs/xval-dfsms-vtam.md) | XVal · Curator · Nexus（改名前的设计稿） |
| [trace-bridge/spec.md](trace-bridge/spec.md) | Chronicle：A2A ↔ MCP 追踪上下文桥 |

## 相关

- [MAEA Framework](https://github.com/deeparchi-ai/MAEA-Framework) — AEG 的组织面（编制、章程、拓扑校验、交叉验证）
- [docs/subsystems.md](docs/subsystems.md) — 14 个子系统全表、实现仓库、测试数
- [a2a-go](https://github.com/a2aproject/a2a-go) — A2A 协议 Go SDK（含 Chronicle 追踪）

---

> *DeepArchi Team · MIT License*
