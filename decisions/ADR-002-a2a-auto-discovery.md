# ADR-002: A2A 协议自动发现

**状态**：采纳  
**日期**：2026-07-14  
**决策者**：sg-architect  
**来源**：MAEA 框架（A2A 协议规范）  

---

## 上下文

MACS 需要知道哪些 Agent 存在。两种方式：手动注册（配置文件列出 Agent 地址）和自动发现（通过注册中心查询）。MAEA 已有 maea-server-cards 注册服务和 A2A 协议。

## 决策

MACS 通过 maea-server-cards 注册中心 + A2A agent.json 端点自动发现 Agent，不做手动注册。

## 理由

1. **MAEA 已有基础设施**：maea-server-cards 在 :9091 运行，返回 Agent 卡片
2. **零配置**：新增 Agent 自动出现在 MACS，删除 Agent 自动消失
3. **协议标准**：A2A 的 `/.well-known/agent.json` 是标准发现端点

## 后果

| 影响 | 描述 |
|------|------|
| 正面 | 零手动配置，Agent 增删自动感知 |
| 负面 | 依赖 maea-server-cards 可用，注册中心挂了 MACS 成瞎子 |
| 风险 | maea-server-cards 当前是静态 JSON，需升级为动态注册才能支持真正的自动发现 |

## 备选方案

| 方案 | 评估 | 原因 |
|------|:----:|------|
| A: 手动 YAML 配置文件 | ❌ | 每次新增 Agent 需改配置，OPC 场景下 Agent 数量增长快 |
| B: mDNS/广播发现 | ❌ | WSL 网络环境下不可靠，需额外网络配置 |
