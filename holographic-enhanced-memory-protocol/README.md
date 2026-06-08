# Holographic Enhanced Memory Protocol

> Hermes 原生 holographic 记忆插件的机制增强版。
>
> *A mechanically enhanced edition of Hermes' native holographic memory plugin.*

原生 holographic 给了积木：SQLite + FTS5 + 实体解析。但把「什么时候记、记什么、记多少」全交给了 prompt 指令——软约束，Agent 可以跳过。本协议在零新依赖的前提下，将软约束全部替换为挂钩系统原生机制的硬约束。

*The native plugin provides the building blocks, but leaves memory decisions to prompt — soft constraints the agent can skip. This protocol replaces every soft constraint with hard hooks. Zero new dependencies.*

---

## 五项核心增强 · Five Core Enhancements

### 一、系统级强约束记忆触发 · System-Level Enforced Memory Hooks

三锚点闭合，Agent 绕不过去。不是建议，是机制。

- **写入锚点 · Write Anchor** — `on_memory_write`：每次 memory 工具调用，钩子机械触发
- **会话锚点 · Session Anchor** — `on_session_finalize`：每次 `/new`、`/reset`、超时断连，自动蒸馏
- **启动锚点 · Startup Anchor** — `initialize`：每次 session 启动强制检查存量，超限当场下沉

*Three anchors, closed loop. The agent cannot bypass them. Not advice — mechanism.*

### 二、热/温/冷三层梯度记忆 · Hot / Warm / Cold Gradient Memory

| 层 | 温度 | 认知对应 | 存储 | 机制 |
|---|------|---------|------|------|
| L0 热记忆 | 🔥 活跃 | 前额叶工作记忆 | MEMORY.md | 全量注入；超限梯度下沉 |
| L1 温记忆 | 🌤 可唤醒 | 海马体结构化 | SQLite + TF-IDF | 信号分类 + 信任评分 + 语义检索 |
| L2 冷记忆 | ❄ 归档 | 皮层情景记忆 | session_search | 对话原文，手动回溯 |

下沉不是删除，是降级。用进废退。

*Sinking is degradation, not deletion. Use it or lose it.*

### 三、TF-IDF 语义检索 · TF-IDF Semantic Retrieval

用 TF-IDF 向量化 + cosine similarity 替代 FTS5 作为主检索手段。中文字符 bigram + 英文单词 token。numpy only，零 API 调用。

| 查询 | FTS5（旧） | TF-IDF（新） |
|------|-----------|-------------|
| "记忆机制" | 0 条 ❌ | Holographic Memory Protocol ✅ |
| "有什么教训" | 0 条 ❌ | 三戒 + 不要跳步 ✅ |

*TF-IDF vectorization + cosine similarity replaces FTS5. Mixed Chinese/English tokenization. numpy only.*

### 四、极致轻量 · Radical Lightness

零新服务、零新数据库、零新依赖。全部增强在 SQLite + 文件系统之上。分类是正则，下沉是文件读写，评分是计数器——所有机械操作由代码完成，不消耗 LLM token。

*Zero new services, databases, or dependencies. All mechanical operations are code-driven — zero LLM token cost.*

### 五、L0/DB 解耦 + 健壮性保障（v2.5.1） · L0/DB Decoupling + Resilience

核心原则：热层（L0, MEMORY.md）必须独立于温层（L1, SQLite）运行。

- **WAL 竞态重试**：MemoryStore 创建失败时自动重试 3 次（100ms/200ms backoff）
- **启动下沉始终执行**：`_enforce_l0_limit()` 只依赖文件系统，不依赖数据库。即使 SQLite 完全不可用，MEMORY.md 也不会无限增长

*The hot layer must NEVER depend on the warm layer. Startup sinking always runs — filesystem only, no DB required.*

---

## 版本 · Changelog

| Version | Date | Change |
|---------|------|--------|
| 2.5.1 | 2026-06-08 | L0/DB 解耦 + WAL 竞态重试 |
| 2.5.0 | 2026-06-07 | TF-IDF 语义检索 |
| 2.4.0 | 2026-06-06 | 诊断工具与故障分析 |
| 2.3.0 | 2026-06-05 | 阈值校准 1600→2200 |
| 2.0.0 | 2026-06-05 | 初始发布 |

完整文档见 [SKILL.md](SKILL.md)。
