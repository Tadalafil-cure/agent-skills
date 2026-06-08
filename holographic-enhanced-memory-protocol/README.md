# Holographic Enhanced Memory Protocol

> Hermes 原生 holographic 记忆插件的机制增强版 — 系统级强约束记忆触发、热/温/冷三层梯度记忆、TF-IDF 语义检索、类脑记忆下沉与用进废退淘汰。零新依赖，同等轻量。
>
> *A mechanically enhanced edition of Hermes' native holographic memory plugin — system-level enforced memory hooks, hot/warm/cold gradient memory, TF-IDF semantic retrieval, and brain-inspired memory sinking with use-it-or-lose-it pruning. Zero new dependencies.*

---

## 五大核心特色 · Five Core Features

### 一、系统级强约束记忆触发 · System-Level Enforced Memory Hooks

不再是 prompt 里一句「请记住用户偏好」。每一个关键节点都锚定在 Hermes 的系统机制上，三锚点闭合，Agent 绕不过去。

- **写入锚点** — `on_memory_write`：每次 memory 工具调用，钩子机械触发。写入即分类，写入即镜像，写入即检查容量。
- **会话锚点** — `on_session_finalize`：每次 `/new`、`/reset`、超时断连，自动蒸馏会话内容、修剪废弃记忆。
- **启动锚点** — `initialize`：每次 session 启动强制检查存量，超限当场下沉——不留历史债务。

*Write → classify → mirror → capacity check, all in one unbroken chain. The agent cannot skip it. Not advice — mechanism.*

### 二、热/温/冷三层梯度记忆 · Hot / Warm / Cold Gradient Memory

借鉴认知科学的记忆衰减过程，将扁平存储重组为三层：

| 层 | 温度 | 认知对应 | 存储 | 机制 |
|---|------|---------|------|------|
| L0 热记忆 · Hot | 🔥 活跃 | 前额叶工作记忆 | MEMORY.md | 全量注入；超限梯度下沉 |
| L1 温记忆 · Warm | 🌤 可唤醒 | 海马体结构化 | SQLite + TF-IDF | 信号分类 + 信任评分 + 语义检索 |
| L2 冷记忆 · Cold | ❄ 归档 | 皮层情景记忆 | session_search | 对话原文，手动回溯 |

**下沉不是删除，是降级**——多次不被唤醒的事实持续衰减，直到自动清理。用进废退的工程实现。

*Sinking is degradation, not deletion. Use it or lose it.*

### 三、TF-IDF 语义检索 · TF-IDF Semantic Retrieval

FTS5 关键词搜索存在词汇不对齐问题——用户说「记忆机制」，事实写的是「holographic memory protocol」，关键词永远匹配不上。

本协议用 TF-IDF 向量化 + cosine similarity 替代 FTS5 作为主检索手段。中文字符 bigram + 英文单词 token，numpy only，零 API 调用。

| 用户查询 | FTS5（旧） | TF-IDF（新） |
|----------|-----------|-------------|
| "记忆机制" | 0 条 ❌ | Holographic Memory Protocol ✅ |
| "有什么教训" | 0 条 ❌ | 三戒 + 不要跳步 ✅ |
| "模型怎么切换" | 0 条 ❌ | 模型路由 + thinking 三档 ✅ |

### 四、极致轻量 · Radical Lightness

零新服务、零新数据库、零新依赖。全部增强在 SQLite + 文件系统之上。分类是正则，下沉是文件读写，评分是计数器，检索是 numpy 矩阵运算——所有机械操作由代码完成，不消耗 LLM token。适合离线环境、单机部署、嵌入式设备。

*Zero new services, databases, or dependencies. All mechanical operations are code-driven — zero LLM token cost.*

### 五、L0/DB 解耦 + 健壮性保障（v2.5.1 新增） · L0/DB Decoupling + Resilience

**核心设计原则：热层（L0, MEMORY.md）必须独立于温层（L1, SQLite）运行。**

在网关环境下，每条消息创建新 Agent → 新 MemoryStore。前一个 Agent 的 `shutdown()` 关闭 SQLite 连接时，WAL checkpoint 是异步的——下一个 Agent 的 `initialize()` 可能在锁释放前就启动了。

v2.5.1 的两项硬修复：

1. **WAL 竞态重试**：MemoryStore 创建失败时自动重试 3 次（100ms/200ms backoff），覆盖 WAL 锁释放窗口。
2. **L0/DB 解耦**：`_enforce_l0_limit()` 始终运行——即使 SQLite 完全不可用。下沉只需要文件系统，不依赖数据库。`_mark_sunk()` 在 `self._store is None` 时优雅返回。MEMORY.md 永远不会无限增长。

**验证**：模拟完整 DB 故障（FakeStore 始终抛异常），MEMORY.md 从 3642 字符（15 条，紧急级别）成功降至 2428 字符（10 条，下沉 5 条）——在 `provider._store is None` 的条件下完成。

*The hot layer (L0, MEMORY.md) must NEVER depend on the warm layer (L1, SQLite). They are independent layers — the hot layer remains operational even when the warm layer is unavailable.*

---

## 快速开始 · Quick Start

详见 [SKILL.md](SKILL.md) — 五个补丁覆盖 holographic 插件核心、语义嵌入引擎、检索管线、agent loop 桥接。

*See [SKILL.md](SKILL.md) — five patches spanning the holographic plugin core, embedding engine, retrieval pipeline, and agent loop bridge.*

## 版本 · Changelog

| Version | Date | Change |
|---------|------|--------|
| 2.5.1 | 2026-06-08 | L0/DB 解耦：`_enforce_l0_limit()` 始终运行；WAL 竞态重试（3× with backoff）；热层独立于温层 |
| 2.5.0 | 2026-06-07 | TF-IDF 语义检索：embedding 列、增量索引、cosine similarity |
| 2.4.0 | 2026-06-06 | 诊断工具：健康检查脚本、"database is locked" 故障分析 |
| 2.3.0 | 2026-06-05 | 阈值校准：soft 1200→1600, emergency 2000→2200 |
| 2.0.0 | 2026-06-05 | 初始发布：on_memory_write 镜像、信任评分、FTS5+HRR |
