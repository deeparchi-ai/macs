# MACS 架构决策记录

本目录采用轻量 ADR（Architecture Decision Record）格式，记录 MACS 的每条架构决策。

## 约定

- 编号连续（ADR-001 起）
- 状态四态：提议 → 采纳 / 废弃 / 延后至 vX.Y
- 每条不超过一页
- 与 MAEA 框架吸收联动：框架吸收新成果 → 触发 MACS ADR 评估

## 索引

| ADR | 标题 | 状态 | 日期 |
|-----|------|:----:|------|
| [001](ADR-001-readonly-observability.md) | 只读不控制 | ✅ | 2026-07-14 |
| [002](ADR-002-a2a-auto-discovery.md) | A2A 自动发现 | ✅ | 2026-07-14 |
| [003](ADR-003-six-dimension-audit.md) | 六维对账审计 | ✅ | 2026-07-14 |
| [004](ADR-004-token-budget-alerts.md) | Token 预算两级告警 | ✅ | 2026-07-14 |
| [005](ADR-005-sqlite-to-postgresql.md) | SQLite → PostgreSQL | ✅ | 2026-07-14 |
| [006](ADR-006-maea-macs-decoupling.md) | MAEA 框架与 MACS 实现解耦 | ✅ | 2026-07-18 |

## 触发规则

以下事件触发新增 ADR：
1. MAEA 框架吸收了新外部参考（如 Palantir Foundry 的资源隔离模型）
2. MACS 实现中需要做出不可逆的技术选择
3. 用户/社区提出与现有 ADR 冲突的需求
