# ADR-006: MAEA 框架与 MACS 实现解耦

**状态**：采纳  
**日期**：2026-07-18  
**决策者**：sg-architect（邝谧确认）  
**来源**：MAEA 框架治理  

---

## 上下文

MAEA 是方法论框架（持续吸收外部架构成果：Palantir/CICS/WLM/TOGAF 等），MACS 是具体实现。需要定义两者的关系：框架中的每条设计原则是否都应进入 MACS？

邝谧明确指示：MAEA 框架来者不拒（理论上都能吸收），MACS 是否采用独立评估。

## 决策

**MAEA 框架与 MACS 实现完全解耦**，通过 ADR 机制管理"吸收→采纳"过程：

1. **MAEA 框架**：持续吸收成熟架构参考，写入 MAEA-Framework/docs/ 或 specs/
2. **sg-architect 评估**：每次框架吸收新成果，触发一条 ADR，决定 MACS 采纳/延后/不采纳
3. **MACS Roadmap**：延后的决策记录到 MACS DESIGN.md Roadmap 对应版本

## 理由

1. **防止框架膨胀驱动实现膨胀**：框架吸收 50 条原则 ≠ MACS 要实现 50 条
2. **版本化采纳**：某条原则可能在 v0.1 不需要但 v1.0 需要
3. **可追溯**：每条不采纳/延后的决策都有记录，后续可以重新评估

## 后果

| 影响 | 描述 |
|------|------|
| 正面 | 框架自由吸收，实现轻量聚焦。决策可追溯 |
| 负面 | 每条新吸收需额外写 ADR |
| 风险 | 如果 ADR 积压不写，解耦退化 |

## 流程

```
外部架构成果
  → MAEA-Framework/docs/ 写入
  → sg-architect 评估
  → MACS/decisions/ADR-NNN.md
  → 采纳 → MACS 实现
  → 延后 → MACS DESIGN.md Roadmap
  → 不采纳 → ADR 记录原因
```
