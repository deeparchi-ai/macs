# 子系统全表 — 14 个子系统

> 本页是从 README 首屏移出的明细：14 个子系统、实现仓库、测试数与 IBM z/OS 对照。
>
> **z/OS 对照是工程注释，不是等价声明**：只用来标出各子系统在职责分工上的位置，
> 不表示与任何 IBM 产品存在实现继承、兼容或授权关系。
>
> **测试数口径**：实现仓库 `*_test.go` 中顶层 `func Test*` 的个数（不含子用例、Example、Fuzz）。
> 核对方式与时间：2026-11-15 逐仓库 `git clone --depth 1` 后计数；本仓库内 `tests/*.py` 计 `def test_*`。
> 数字与仓库现状不一致时**以仓库为准**，请提 PR 修正本页。

## 状态三档

| 档 | 含义 |
|---|---|
| **可用** | 有实现仓库，主路径可运行 |
| **部分** | 有实现，但规格中的能力未全部完成（本页「未完成」列写明缺口） |
| **POC** | 只有原型或单点脚本，未产品化 |

## 全表

| § | 子系统 | 角色 | z/OS 对照（工程注释） | 状态 | 未完成 | 实现仓库 | 测试 |
|:--:|------|------|-----------|:--:|------|-----------|:--:|
| §2 | **Regulator** | 目标调度 + Token 预算 + 模型故障切换 | WLM — Workload Manager | 部分 | Token 预算 | [macs-regulator-go](https://github.com/deeparchi-ai/macs-regulator-go) | 98 |
| §3 | **Sanctum** | 访问控制 + 信任评分 + 硬约束 | RACF — Resource Access Control Facility | 部分 | trust scoring | [macs-sanctum-go](https://github.com/deeparchi-ai/macs-sanctum-go) | 28 |
| §3b | **Loom** | 因果 DAG 回滚 + 两阶段提交 | CICS Syncpoint | 可用 | — | [macs-loom-go](https://github.com/deeparchi-ai/macs-loom-go) | 12 |
| §4 | **Chronicle** | 证据留痕 + W3C 追踪 + 跨协议桥 | SMF — System Management Facilities | 可用 | — | [mcp-audit-go](https://github.com/deeparchi-ai/mcp-audit-go) · [chronicle-bridge-go](https://github.com/deeparchi-ai/macs-chronicle-bridge-go) · [a2a-go PR #377](https://github.com/a2aproject/a2a-go/pull/377) · DUMP（本仓库） | 52 † |
| §5 | **XVal** | 交叉验证 + 供应商故障切换 | （agent 原生，无 IBM 血缘） | 可用 | — | [macs-xval-go](https://github.com/deeparchi-ai/macs-xval-go) | 32 |
| §6 | **Cadence** | 批调度 + 作业输出管理 | JES2 — Job Entry Subsystem + SDSF | POC | — | [jes-gate](https://github.com/deeparchi-ai/macs/tree/main/integrations/jes-gate) | — ‡ |
| §7 | **Curator** | 知识生命周期 + 压缩 + 备份 | DFSMS + DFSMSdss | 可用 | — | [macs-curator-go](https://github.com/deeparchi-ai/macs-curator-go) | 27 |
| §8 | **Nexus** | 协议准入 + 多传输路由 | VTAM — Virtual Telecommunications Access Method | 可用 | — | [macs-nexus-go](https://github.com/deeparchi-ai/macs-nexus-go) | 85 |
| §9 | **Gauge** | 性能度量 + 跨供应商健康 | RMF + NetView | 可用 | — | [macs-gauge-go](https://github.com/deeparchi-ai/macs-gauge-go) | 18 |
| §10 | **Seal** | 身份注册 + 证书 + 签名 | ICSF — Integrated Cryptographic Service Facility | 可用 | — | [macs-seal-go](https://github.com/deeparchi-ai/macs-seal-go) | 17 |
| §11 | **Relay** | 集群状态 + 共享状态 + 广播 | XCF — Cross-system Coupling Facility | 可用 | — | [macs-relay-go](https://github.com/deeparchi-ai/macs-relay-go) | 16 |
| §12 | **Warden** | 崩溃恢复 + 策略运维 + 升级 | ARM + System Automation | 可用 | — | [macs-warden-go](https://github.com/deeparchi-ai/macs-warden-go) | 13 |
| §13 | **Pulse** | 自健康检查 + 启动一致性 | Health Checker | 可用 | — | [macs-pulse-go](https://github.com/deeparchi-ai/macs-pulse-go) | 10 |
| §14 | **Console** | 操作控制台 | TSO + ISPF | 可用 | — | [macs-console-go](https://github.com/deeparchi-ai/macs-console-go) | 36 |

† §4 合计 52 = mcp-audit-go 10 + chronicle-bridge-go 13 + 本仓库 DUMP `tests/*.py` 29；
上游 [a2a-go PR #377](https://github.com/a2aproject/a2a-go/pull/377) 的测试数未单独计数，故不计入合计。

‡ §6 jes-gate 是仓库内单文件脚本（`integrations/jes-gate/jes-gate`），无测试文件，故本列记「—」。

## 本仓库自带的验证

| 位置 | 内容 |
|---|---|
| `tests/`（29 个测试函数） | DUMP 采集器、sink、触发器、信号、Hermes 适配器、vendored 插件 |
| `poc/*_test.go`（37 个测试函数） | 三模型故障切换、崩溃恢复、身份生命周期、集群协同、Token 预算、跨供应商 |

两处均为 `go test` / `pytest` 可执行，不是纸面声明。

## 规格

- 治理规格总纲：[MACS Governance Specification v3.0](https://github.com/deeparchi-ai/MAEA-Framework/blob/main/specs/macs-governance-spec.md)
- 子系统设计稿：[security-model.md](../specs/security-model.md) · [state-rollback.md](../specs/state-rollback.md) · [xval-dfsms-vtam.md](../specs/xval-dfsms-vtam.md) · [trace-bridge/spec.md](../trace-bridge/spec.md)
