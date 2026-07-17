# MACS POC Scenarios

> 13 子系统集成验证场景。每个场景横跨多个子系统，模拟真实多 Agent 运行态。

---

## POC-1: 三模型分歧 → 多数决 → 故障转移

**覆盖**: §5 XVal + §9 Gauge + §12 Warden + §4 Chronicle

**场景**: 策略 Agent 输出被三个模型交叉验证。

```
Step 1 — 正常三模型裁决
  Primary (Anthropic Opus):  confidence=0.92  ✓ (agree with audit)
  Audit   (DeepSeek V4):    confidence=0.88  ✓ (agree with primary)
  Tertiary (Gemini 2.5):    confidence=0.50  ✗ (dissents)

  → XVal 判: TriMajority (2/3)
  → L2 flagged + execute（多数意见执行，少数意见记录供人审）
  → Chronicle 写入审计收据（三条模型输出 + 裁决结果）

Step 2 — Primary 故障
  Gauge 检测: anthropic API 错误率 > 10%（5分钟窗口）
  → Warden 收到 "vendor-degraded" 事件
  → XVal Failover: Audit 提升为 Primary，Tertiary 提升为 Audit
  → 降级为 2-model + L0 self-critique 模式
  → Relay 广播 "xval-degraded" → 所有 Agent 知悉

Step 3 — 全厂商故障
  Gauge 检测: 三个厂商全部不可用
  → CrossVendorCorrelation.Score = 0.95（高度相关 → 外部原因）
  → Warden 触发 "vendor-total-outage" 策略
  → 全局暂停 + 通知人类
```

**验证点**:
- [ ] 2/3 多数决正确执行
- [ ] 故障转移链: 3→2→1→0 逐级降级
- [ ] 跨厂商相关性检测触发（非厂商特定故障）
- [ ] Chronicle 审计收据包含完整三模型输出

---

## POC-2: Agent 崩溃 → 恢复 → 重放

**覆盖**: §12 Warden + §11 Relay + §7 Curator + §3b Loom + §4 Chronicle

**场景**: 研究 Agent 在执行多步任务时崩溃。

```
Step 1 — 正常执行
  research-agent 执行 3 步任务链:
    Step A: 搜索资料 (Loom fork-point @ t₁)
    Step B: 分析数据 (Loom fork-point @ t₂)
    Step C: 撰写报告 ← 崩溃！

Step 2 — 崩溃检测
  Warden CrashDetector: research-agent 5s 无心跳
  → RecordFailure("research-agent") → crash-loop? false (首次)
  → Relay 广播 "agent-crashed: research-agent"
  → 依赖方 Agent 暂停向 research-agent 委派任务

Step 3 — 恢复
  Warden RecoveryPlan:
    1. DUMP 快照（当前内存状态）
    2. 重启 research-agent
    3. Curator 从热层恢复上下文（Tier 0 → 完整 fidelity）
    4. Loom 从 fork-point t₂ 重放
    5. 重试 Step C

Step 4 — 崩溃循环（3 次 / 5 分钟）
  → Warden PolicyEngine 匹配 "agent-crash-loop"
  → 动作: [suspend_agent, notify_human, escalate_after(30m)]
  → EscalationChain: L0 → L1 → L2 → L3（30分钟无人响应 → 升级）
```

**验证点**:
- [ ] 心跳超时检测正确
- [ ] Relay 广播暂停委派
- [ ] Curator 热层恢复 + Loom fork-point 重放
- [ ] 崩溃循环策略触发（3次/5分钟）
- [ ] EscalationChain 逐级升级

---

## POC-3: 身份全生命周期

**覆盖**: §10 Seal + §3 Sanctum

**场景**: 新 Agent 注册、运行、轮换密钥、被撤销。

```
Step 1 — 注册
  new-agent 提交 A2A Agent Card
  → Seal.Register: LUName="code-reviewer.prod"
  → 校验 four-name alignment (Card 内名称一致)
  → TrustRoot 绑定（首次 pin，后续轮换需人审）
  → Sanctum 创建初始信任分数 = 0.5（新 Agent，中性）

Step 2 — 签名输出
  code-reviewer 审查 PR #42:
    输出: "APPROVE: LGTM, no issues found"
  → Seal.Sign(trustRoot, payload) → SignedOutput
  → 下游 Agent: Seal.Verify(output, trustRoot) → ✓

Step 3 — 证书轮换
  code-reviewer 密钥即将过期
  → Seal.BeginRotation("code-reviewer.prod", newKey, overlap=1h)
  → 旧密钥 + 新密钥 同时有效（overlap 窗口）
  → 1h 后: Seal.CompleteRotation → 旧密钥失效

Step 4 — 撤销
  检测到异常行为（Sanctum 信任分数 < 0.2）
  → Seal.Revoke("code-reviewer.prod", "trust score below threshold")
  → 立即: 所有活跃会话终止
  → Chronicle 记录撤销原因
  → 后续 Seal.Verify → ✗ (agent revoked)
```

**验证点**:
- [ ] 注册 + TrustRoot 绑定
- [ ] 签名/验签正确
- [ ] 证书轮换 overlap 窗口无停机
- [ ] 撤销后验签失败

---

## POC-4: 集群协调 → 故障传播

**覆盖**: §11 Relay + §12 Warden + §13 Pulse

**场景**: 多个 Agent 组成集群，一个宕机后的协调恢复。

```
Step 1 — 集群建立
  agents = {architect, researcher, coder, reviewer}
  各 Agent 启动时:
    → Relay.Cluster.Join(member)
    → Relay.Cluster.Heartbeat(member) 每 5s
    → Relay.Broadcast.Subscribe("model-change")
    → Relay.Broadcast.Subscribe("agent-status")

Step 2 — 共享状态
  architect 写入共享状态:
    Relay.SharedState.Put("current-model", "claude-opus-4", ttl=1h)
  researcher 读取:
    Relay.SharedState.Get("current-model") → "claude-opus-4"

Step 3 — coder 宕机
  Relay.Cluster.DetectStale(timeout=15s) → [coder]
  → Relay.Broadcast.Publish("agent-status", "coder:offline")
  → architect + researcher + reviewer 收到通知
  → GroupComm: 从 "active-deploy" 组移除 coder

Step 4 — Pulse 健康传播
  Pulse 检测: coder 子系统 3 次连续心跳失败
  → DependencyGraph.Propagate("coder"):
      affected = {reviewer: "depends on coder", deploy-pipeline: "depends on coder"}
  → Pulse.Status → Degraded（非关键子系统故障）
  → Warden 触发恢复流程
```

**验证点**:
- [ ] 集群成员心跳 + 过期检测
- [ ] 共享状态 TTL 过期
- [ ] 广播通知所有在线成员
- [ ] Pulse 依赖图递归传播

---

## POC-5: 策略引擎决策链

**覆盖**: §12 Warden + §2 Regulator + §9 Gauge

**场景**: Token 预算耗尽 → 策略自动降级。

```
预定义策略:
  policies:
    - name: token-budget-yellow
      condition: regulator.level == "YELLOW"
      actions: [notify_owner, reduce_audit_sampling]
      escalation: L1

    - name: token-budget-red
      condition: regulator.level == "RED"
      actions: [suspend_l2_l3_agents, notify_owner]
      escalation: L2

    - name: token-budget-black
      condition: regulator.level == "BLACK"
      actions: [allow_l1_only, notify_human, escalate_after(30m)]
      escalation: L3

Step 1 — YELLOW
  Regulator 报告: 当日 Token 消耗 > 70%
  → Warden.PolicyEngine.Evaluate(state)
  → 匹配 "token-budget-yellow"
  → 动作: 通知 owner + 降低 XVal 抽样率 0.1→0.05

Step 2 — RED
  消耗 > 90%
  → 匹配 "token-budget-red"
  → 动作: 挂起 L2/L3 Agent + 通知

Step 3 — BLACK
  消耗 > 100%
  → 匹配 "token-budget-black"
  → 仅 L1（架构/战略）Agent 继续
  → EscalationChain: L3 → 30min 无人响应 → 通知人类
```

**验证点**:
- [ ] 策略条件 DSL 解析正确（>=, >, ==, <, <=）
- [ ] 多策略同时触发
- [ ] EscalationChain 超时升级

---

## POC-6: 跨厂商相关退化检测

**覆盖**: §9 Gauge + §12 Warden + §5 XVal

**场景**: 区分 "厂商自身故障" vs "外部基础设施故障"。

```
Case A — 厂商自身故障（Anthropic 单独退化）
  Gauge 指标流（过去 5 分钟）:
    anthropic:  [0.99, 0.98, 0.95, 0.91, 0.88]  ← 缓慢退化
    deepseek:   [0.97, 0.98, 0.97, 0.96, 0.97]  ← 正常
    google:     [0.95, 0.96, 0.94, 0.95, 0.96]  ← 正常

  → Pearson(anthropic, deepseek) = 0.12  (低相关)
  → Pearson(anthropic, google)   = 0.08  (低相关)
  → CrossVendorCorrelation.Score = 0.12
  → 结论: 厂商自身问题。触发 Anthropic 故障转移。

Case B — 外部基础设施故障（全部同时退化）
  Gauge 指标流:
    anthropic:  [0.99, 0.95, 0.88, 0.72, 0.51]  ← 快速退化
    deepseek:   [0.98, 0.94, 0.86, 0.70, 0.48]  ← 同步退化
    google:     [0.97, 0.93, 0.85, 0.68, 0.45]  ← 同步退化

  → Pearson(anthropic, deepseek) = 0.94  (高度相关!)
  → Pearson(anthropic, google)   = 0.91  (高度相关!)
  → CrossVendorCorrelation.Score = 0.94
  → 结论: 外部基础设施故障。不触发厂商故障转移。
  → Warden 触发 "vendor-total-outage" → 全局暂停 + 通知人类
```

**验证点**:
- [ ] Pearson 相关系数计算正确
- [ ] 厂商自身故障 vs 外部故障区分
- [ ] 不同场景触发不同 Warden 策略

---

## 实施建议

| POC | 复杂度 | 涉及子系统 | 预估 Go 代码 |
|:---:|:---:|------|:--:|
| POC-1 | ⭐⭐⭐ | XVal + Gauge + Warden + Chronicle | ~150 行 |
| POC-2 | ⭐⭐⭐⭐ | Warden + Relay + Curator + Loom | ~200 行 |
| POC-3 | ⭐⭐ | Seal + Sanctum | ~100 行 |
| POC-4 | ⭐⭐ | Relay + Warden + Pulse | ~120 行 |
| POC-5 | ⭐ | Warden + Regulator | ~80 行 |
| POC-6 | ⭐⭐ | Gauge + Warden + XVal | ~120 行 |

**推荐实施顺序**: POC-5（最简单，验证策略引擎）→ POC-6（验证 Gauge 核心能力）→ POC-3（Seal 全生命周期）→ POC-1（三模型 + 故障转移，核心场景）→ POC-4（集群协调）→ POC-2（崩溃恢复，最复杂）
