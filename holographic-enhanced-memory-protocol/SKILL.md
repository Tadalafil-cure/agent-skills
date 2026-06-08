---
name: holographic-enhanced-memory-protocol
description: "Hermes 原生 holographic 插件的机制增强版 — 系统级强约束记忆触发、热/温/冷三层梯度记忆、TF-IDF 语义检索、类脑记忆下沉与用进废退淘汰。零新依赖，同等轻量。 / A mechanically enhanced edition of Hermes' native holographic plugin — system-level enforced memory hooks, hot/warm/cold gradient memory, TF-IDF semantic retrieval, and brain-inspired memory sinking with use-it-or-lose-it pruning. Zero new dependencies."
version: 2.5.1
---

# Holographic Enhanced Memory Protocol

> *English version follows the Chinese below. 英文版在中文之后。*

**Hermes 原生 holographic 记忆插件的机制增强版。**

原生 holographic 给了积木：SQLite 结构化存储 + FTS5 全文检索 + 实体解析。
但它把「什么时候记、记什么、记多少」全部交给了 prompt 指令——软约束，Agent
可以跳过，也可以乱写。本协议在零新依赖的前提下，将软约束全部替换为挂钩系统
原生机制的硬约束，并引入热/温/冷三层梯度记忆模型 + TF-IDF 语义检索。

---

**A mechanically enhanced edition of Hermes' native holographic memory plugin.**

The native holographic plugin provides the building blocks: SQLite structured
storage, FTS5 full-text search, and entity resolution. But it leaves *when to
remember, what to remember, and how much to keep* entirely to prompt
instructions — soft constraints the agent can skip or abuse. This protocol
replaces every soft constraint with hard hooks anchored in Hermes' native
mechanisms, and introduces a hot/warm/cold gradient memory model with TF-IDF
semantic retrieval. Zero new dependencies.

---

## 四项核心增强 · Four Core Enhancements

### 一、系统级强约束记忆触发
### Ⅰ. System-Level Enforced Memory Hooks

不再是 prompt 里一句「请记住用户偏好」。每一个关键节点都锚定在 Hermes 的
系统机制上：

No more "please remember user preferences" buried in a prompt. Every critical
trigger point is anchored in Hermes' native mechanisms:

- **写入锚点 · Write Anchor** — `on_memory_write`：Agent 每次调用 memory 工具，钩子机械触发，
  不可跳过。写入即分类，写入即镜像，写入即检查容量。
  *Fires mechanically on every memory tool call — the agent cannot skip it.
  Write → classify → mirror → capacity check, all in one unbroken chain.*

- **会话锚点 · Session Anchor** — `on_session_finalize`：每次 `/new`、`/reset`、超时断连，
  钩子自动蒸馏会话内容、修剪废弃记忆。Agent 不需要「记得去整理」。
  *Auto-distills conversation content and prunes abandoned facts at every
  session boundary. The agent doesn't need to "remember to clean up."*

- **启动锚点 · Startup Anchor** — `initialize`：每次 session 启动时强制检查存量，
  超限当场下沉——不留历史债务。
  *Enforces existing capacity on every session start. No accumulated backlog.*

三个锚点闭合，Agent 绕不过去。不是建议，是机制。
*Three anchors, closed loop. The agent cannot bypass them. Not advice — mechanism.*

### 二、热/温/冷三层梯度记忆
### Ⅱ. Hot / Warm / Cold Gradient Memory

借鉴认知科学中人类记忆从活跃到归档的自然衰减过程，将 holographic 的扁平
存储重组为三层，每层有明确的「温度」和淘汰策略：

Inspired by the natural decay of human memory from active awareness to deep
archival, holographic's flat storage is reorganized into three layers, each
with a distinct "temperature" and eviction strategy:

| 层 · Layer | 温度 · Temp | 认知对应 · Cognitive Analog | 存储 · Storage | 机制 · Mechanism |
|------------|------------|---------------------------|----------------|-----------------|
| L0 热记忆 · Hot | 🔥 活跃 Active | 前额叶工作记忆 · Prefrontal working | MEMORY.md | 全量注入；超限梯度下沉 · Full injection; gradient sink when over limit |
| L1 温记忆 · Warm | 🌤 可唤醒 Retrievable | 海马体结构化 · Hippocampal structured | SQLite + TF-IDF | 信号分类 + 信任评分 + 语义检索 · Classified, trust-scored, semantic retrieval |
| L2 冷记忆 · Cold | ❄ 归档 Archived | 皮层情景记忆 · Cortical episodic | session_search | 完整对话原文，手动回溯 · Raw transcripts, manual recall |

**记忆下沉不是删除，是降级**——就像人脑不会真正「忘记」，只是从活跃意识退到
深层存储。下沉到 L1 的事实仍然可检索，只是信任分降低、不再常驻上下文。
多次不被唤醒的事实持续衰减，直到被自动清理——这是「用进废退」的工程实现。

**Sinking is degradation, not deletion.** Just as the human brain doesn't truly
"forget" — it merely demotes from active awareness to deeper storage. Sunk facts
remain retrievable in L1, just at reduced trust and no longer resident in
context. Facts that go unrecalled decay continuously until automatic pruning —
an engineering realization of *"use it or lose it."*

### 三、TF-IDF 语义检索
### Ⅲ. TF-IDF Semantic Retrieval

FTS5 关键词搜索存在词汇不对齐问题：用户说「记忆机制」，事实写的是
「holographic memory protocol」——关键词永远匹配不上，导致 L1 温记忆中
58 条事实有 35 条永远无法被检索到。

FTS5 keyword search suffers from vocabulary mismatch: when the user says
"memory mechanism" but facts say "holographic memory protocol", the keywords
never match. In a real deployment, 35 out of 58 facts were never retrievable
via FTS5.

本协议用 TF-IDF 向量化 + cosine similarity 替代 FTS5 作为主检索手段：

This protocol replaces FTS5 with TF-IDF vectorization + cosine similarity as
the primary retrieval method:

- **中英混合分词**：中文用字符 bigram，英文用单词级 token
  *Mixed Chinese/English tokenization: character bigrams for CJK, word tokens for ASCII*
- **零外部依赖**：numpy only，无 API 调用，无 embedding 服务
  *Zero external dependencies: numpy only, no API calls, no embedding service*
- **增量索引**：每个 `add_fact()` 自动计算并存储向量到 `embedding BLOB` 列
  *Incremental indexing: every add_fact() auto-computes and stores vector*
- **fallback 机制**：embedding 不可用时自动回退到 FTS5
  *Graceful fallback: auto-downgrades to FTS5 if embeddings unavailable*

**效果对比 · Before/After:**

| 用户查询 | FTS5（旧） | TF-IDF（新） |
|----------|-----------|-------------|
| "记忆机制" | 0 条 ❌ | Holographic Memory Protocol ✅ |
| "有什么教训" | 0 条 ❌ | 三戒 + 不要跳步 ✅ |
| "模型怎么切换" | 0 条 ❌ | 模型路由 + thinking 三档 ✅ |
| "域测试流程" | 0 条 ❌ | 域测试教训 + 工作流 ✅ |

### 四、极致轻量
### Ⅳ. Radical Lightness

本协议没有引入任何新服务、新数据库、新依赖。全部增强都发生在 holographic
插件已有的 SQLite + 文件系统之上。分类是正则，下沉是文件读写，评分是计数器，
检索是 numpy 矩阵运算——所有机械操作由代码完成，不消耗 LLM token。
适合离线环境、单机部署、嵌入式设备。

*This protocol introduces zero new services, databases, or dependencies. Every
enhancement runs on holographic's existing SQLite + filesystem stack.
Classification is regex. Sinking is file I/O. Scoring is counters. Retrieval is
numpy matrix math. All mechanical operations are code-driven — zero LLM token
cost. Suitable for offline environments, single-machine deployments, and
embedded devices.*

---

## Quick Start

Apply these patches to a fresh Hermes Agent installation, then restart.
The protocol spans four files — the holographic plugin core, the semantic
embedding engine, the retrieval pipeline, and the agent loop bridge.

### Patch 1: Holographic Plugin Core

**File**: `plugins/memory/holographic/__init__.py`

#### 1a. Add signal classification + tiered sinking limits

Before the `class HolographicMemoryProvider` line, insert:

```python
# --- L0 capacity limits ---
_L0_SOFT_LIMIT = 1600       # chars — begin gentle sinking
_L0_EMERGENCY_LIMIT = 2200  # chars — maximum-effort sinking

# --- Loci-style signal classification ---
_SIGNAL_MAP = [
    (("我是", "我叫", "我的名字", "身份"), "user_pref", "identity"),
    (("喜欢", "习惯", "偏好", "常用", "prefer", "favorite"), "user_pref", "preference"),
    (("原来", "坑", "记住", "注意", "教训", "lesson", "陷阱", "千万别", "必须", "must"), "general", "lesson"),
    (("决定", "选择", "方案", "decided", "chose", "抉择"), "project", "decision"),
    (("项目", "在做", "开发", "project", "building"), "project", ""),
    (("配置", "命令", "API", "环境", "服务器", "server", "config", "deploy", "部署", "安装", "路径"), "tool", ""),
    (("每次都", "总是", "一般", "通常", "always", "usually", "pattern"), "general", "pattern"),
]

_CATEGORY_PRIORITY = {
    "user_pref": 4,   # never sink
    "general":   3,   # high (lessons)
    "project":   2,   # medium
    "tool":      1,   # low (easily re-discovered)
}

_MEMORY_ENTRY_DELIMITER = "\n§\n"

def _classify_signal(content: str) -> tuple[str, str]:
    lowered = content.lower()
    for keywords, category, tags in _SIGNAL_MAP:
        for kw in keywords:
            if kw in lowered:
                return category, tags
    return "general", ""
```

#### 1b. Fix connection leak in initialize()

**Critical**: without this, multiple `initialize()` calls (session restarts)
create new SQLite connections without closing old ones. Leaked connections
hold write locks indefinitely, causing "database is locked" for all subsequent
writes.

```python
    def initialize(self, session_id: str, **kwargs) -> None:
        # ... existing config loading ...

        # Close any pre-existing store to avoid leaking connections.
        # Without this, multiple initialize() calls (e.g. session restarts)
        # create new SQLite connections without closing old ones, eventually
        # causing "database is locked" when leaked connections hold write locks.
        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass
        if self._retriever is not None:
            self._retriever = None

        # Create new store with retry on transient WAL locks.
        # SQLite WAL checkpoints can hold write locks for 100-500ms after
        # close().  Under concurrent access (gateway creates new agent per
        # message), the previous agent's shutdown() may not have released
        # the WAL lock before this agent starts.  Retry with backoff.
        last_error = None
        for attempt in range(3):
            try:
                self._store = MemoryStore(
                    db_path=db_path,
                    default_trust=default_trust,
                    hrr_dim=hrr_dim,
                )
                self._retriever = FactRetriever(
                    store=self._store,
                    temporal_decay_half_life=temporal_decay,
                    hrr_weight=hrr_weight,
                    hrr_dim=hrr_dim,
                )
                last_error = None
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(0.1 * (attempt + 1))

        self._session_id = session_id

        # ALWAYS enforce L0 limits — works on the filesystem and does NOT
        # require the database.  _mark_sunk() gracefully returns when
        # self._store is None.  This ensures MEMORY.md never grows
        # unbounded even when SQLite is temporarily unavailable.
        self._enforce_l0_limit()

        # Re-raise if store creation failed after all retries so the
        # MemoryManager can log the warning.  L0 enforcement above has
        # already run, so MEMORY.md is safe regardless.
        if last_error is not None:
            raise last_error
```

#### 1c. Fix connection leak in shutdown()

```python
    def shutdown(self) -> None:
        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass
        self._store = None
        self._retriever = None
```

#### 1d. Add on_memory_write with classification + sinking + retry

```python
    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if action not in ("add", "replace") or not self._store or not content:
            return
        category, tags = _classify_signal(content)
        last_error = None
        for attempt in range(3):  # 1 initial + 2 retries
            try:
                self._store.add_fact(content, category=category, tags=tags)
                if target == "memory":
                    self._enforce_l0_limit()
                return
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(0.1)
        logger.warning("Holographic memory_write failed after 3 attempts: %s", last_error)
```

#### 1e–1j. Remaining hooks (as in v2.4.0)

- `_enforce_l0_limit()` — tiered sinking (1600→1800→2000→2200)
- `_mark_sunk()` — post-sink fact tagging
- `_prune_low_trust()` — session-end cleanup (<0.15 trust)
- `on_session_finalize()` — auto_extract + prune
- `register()` — hook registration
- `_ProviderCollector.register_hook()` bridge

---

### Patch 2: Semantic Embedding Engine (NEW in 2.5.0)

**File**: `plugins/memory/holographic/embedding.py` (create new)

Full source at `references/embedding.py`. Core components:

```python
class EmbeddingStore:
    """TF-IDF vector index with cosine similarity search."""
    def __init__(self): ...
    def encode(self, text: str) -> np.ndarray: ...    # text → TF vector
    def index_fact(self, fact_id: int, content: str) -> np.ndarray: ...  # store vector
    def rebuild_idf(self) -> None: ...                 # recompute IDF
    def search(self, query: str, top_k=10, trust_scores=None) -> list[tuple[int, float]]: ...
    def vector_to_bytes(self, vec: np.ndarray) -> bytes: ...  # SQLite BLOB
    def bytes_to_vector(self, data: bytes) -> np.ndarray: ...  # deserialize
```

Tokenization: Chinese character bigrams + English word tokens, with
stopword filtering for both languages.

---

### Patch 3: MemoryStore Schema + Indexing

**File**: `plugins/memory/holographic/store.py`

#### 3a. Add embedding column to schema

```sql
CREATE TABLE IF NOT EXISTS facts (
    ...
    hrr_vector      BLOB,
    embedding       BLOB          -- NEW: TF-IDF embedding vector
);
```

#### 3b. Initialize EmbeddingStore at startup

```python
from .embedding import EmbeddingStore

class MemoryStore:
    def __init__(self, ...):
        ...
        self._embeddings: EmbeddingStore | None = None
        self._init_db()

    def _init_db(self):
        ...
        # Migrate: add embedding column if missing
        if "embedding" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN embedding BLOB")
        self._conn.commit()
        # Load existing embeddings
        self._embeddings = EmbeddingStore()
        self._load_embeddings()
```

#### 3c. Auto-compute embedding on add_fact

```python
    def add_fact(self, content, category, tags, trust=None):
        ...
        self._compute_hrr_vector(fact_id, content)
        self._compute_embedding(fact_id, content)  # NEW
        ...
```

#### 3d. Add semantic search entry point

```python
    def search_embeddings(self, query, category=None, min_trust=0.3, limit=10):
        """Semantic search via TF-IDF embedding cosine similarity."""
        if self._embeddings is None or len(self._embeddings) == 0:
            return self.search_facts(query, category, min_trust, limit)  # fallback
        # ... cosine similarity + trust weighting ...
```

#### 3e. Add rebuild_embeddings() for backfill

```python
    def rebuild_embeddings(self) -> int:
        """Backfill embeddings for all facts. Returns count."""
```

---

### Patch 4: FactRetriever — Semantic Search Pipeline

**File**: `plugins/memory/holographic/retrieval.py`

Replace FTS5-based candidate retrieval with embedding-based:

```python
    def search(self, query, category=None, min_trust=0.3, limit=10):
        # Stage 1: Embedding search (semantic, not keyword)
        candidates = self.store.search_embeddings(
            query, category=category, min_trust=min_trust, limit=limit * 3,
        )
        # Stage 2: Re-rank with Jaccard + HRR + trust
        relevance = 0.5 * emb_score + 0.2 * jaccard + 0.3 * hrr_sim
        score = relevance * trust_score
        # Stage 3: Temporal decay (optional)
```

---

### Patch 5: Run Agent Bridge (unchanged from v2.2.2)

**File**: `run_agent.py`

Ensure both `_invoke_tool` AND `_execute_tool_calls_sequential` have the
`on_memory_write` bridge. The sequential path is used by WeChat/Telegram/CLI
and is the #1 reason hooks silently fail.

---

## Verification

After patching and restarting:

```bash
# 1. Check all hooks are present
grep -c 'def on_memory_write\|def on_session_finalize\|def _enforce_l0_limit\|def _classify_signal' \
  ~/.hermes/hermes-agent/plugins/memory/holographic/__init__.py

# 2. Check embedding column exists
sqlite3 ~/.hermes/memory_store.db "PRAGMA table_info(facts);" | grep embedding

# 3. Backfill existing facts
python3 -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path.home() / '.hermes/hermes-agent/plugins/memory/holographic'))
from embedding import EmbeddingStore
import sqlite3
conn = sqlite3.connect(str(Path.home() / '.hermes/memory_store.db'))
rows = conn.execute('SELECT fact_id, content FROM facts').fetchall()
store = EmbeddingStore()
for fid, content in rows:
    store.index_fact(fid, content)
store.rebuild_idf()
for fid, content in rows:
    vec = store._fact_vectors.get(fid)
    if vec is not None:
        conn.execute('UPDATE facts SET embedding = ? WHERE fact_id = ?',
                     (store.vector_to_bytes(vec), fid))
conn.commit()
print(f'Backfilled {len(rows)} facts')
"

# 4. Test semantic search
python3 -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path.home() / '.hermes/hermes-agent/plugins/memory/holographic'))
from embedding import EmbeddingStore
import sqlite3
conn = sqlite3.connect(str(Path.home() / '.hermes/memory_store.db'))
conn.row_factory = sqlite3.Row
store = EmbeddingStore()
for row in conn.execute('SELECT fact_id, content, embedding FROM facts WHERE embedding IS NOT NULL'):
    store._fact_vectors[row['fact_id']] = store.bytes_to_vector(row['embedding'])
    store.index_fact(row['fact_id'], row['content'])
store.rebuild_idf()
for q in ['记忆机制', '有什么教训', '下沉机制']:
    results = store.search(q, top_k=3)
    print(f'{q}:')
    for fid, score in results:
        r = conn.execute('SELECT content FROM facts WHERE fact_id = ?', (fid,)).fetchone()
        print(f'  [{score:.3f}] {r[\"content\"][:80]}')
"

# 5. Verify no connection leaks
fuser ~/.hermes/memory_store.db
# Should show exactly 1 PID with 3 fds (DB + WAL + SHM)
ls /proc/$(pgrep -f 'gateway run')/fd/ | grep -c memory_store
# Should be 3 (one connection)
```

---

## Architecture Reference

### Data Flow (Updated for v2.5.1)

```
Agent calls memory(action='add', content='...')
  │
  ├── _memory_tool() writes MEMORY.md (L0)
  │
  └── on_memory_write() HOOK (unskippable)
        ├── _classify_signal(content) → (category, tags)
        ├── fact_store.add() → L1 mirror (SQLite)
        │     ├── _compute_hrr_vector() → HRR phases
        │     └── _compute_embedding() → TF-IDF vector  ← NEW
        └── _enforce_l0_limit()
              ├── 1600+ chars → gentle   (sink 1)
              ├── 1800+ chars → warning  (sink 2)
              ├── 2000+ chars → urgent   (sink 3)
              └── 2200+ chars → emergency (sink 5)
                    └── _mark_sunk(victim)
                          ├── tag += "sunk"
                          └── trust -= 0.15

User sends message:
  prefetch(query)
    └── FactRetriever.search(query)
          ├── store.search_embeddings(query)  ← PRIMARY (cosine similarity)
          │     └── TF-IDF encode → cosine_sim × trust
          ├── Jaccard rerank (token overlap)
          └── HRR similarity (structural bonus)
    → Top 5 facts injected into system prompt

Session start:
  initialize()
    ├── close old store connection  ← prevents leaks
    ├── MemoryStore() [retry ×3 with backoff]  ← NEW v2.5.1: survives WAL races
    │     ├── Success → FactRetriever(), _load_embeddings()
    │     └── All retries fail → store stays None, error saved
    ├── _enforce_l0_limit()  ← ALWAYS RUNS (decoupled from DB)  ← NEW v2.5.1
    │     ├── File ops only (read/write MEMORY.md)
    │     └── _mark_sunk() skipped if store is None
    └── Re-raise saved error (if any) → MemoryManager logs warning

Session end (/new, /reset, timeout):
  on_session_finalize()
    ├── auto_extract_facts(messages) → trust=0.30
    └── _prune_low_trust() → cull <0.15, cap 200
  shutdown()
    └── self._store.close()  ← NEW (prevents leaks)
```

### Layers

| Layer | Temperature | Cognitive Analog | Storage | Mechanism |
|-------|------------|-----------------|---------|-----------|
| L0 热记忆 · Hot | 🔥 Active | Prefrontal working | MEMORY.md | Full injection; gradient sink when >1600 chars |
| L1 温记忆 · Warm | 🌤 Retrievable | Hippocampal structured | SQLite + TF-IDF vectors | Signal-classified, trust-scored, semantic prefetch |
| L2 冷记忆 · Cold | ❄ Archived | Cortical episodic | SQLite sessions | Raw transcripts, manual recall |

### Trust Lifecycle

```
Active save   → 0.50 → sunk → 0.35 → sunk again → 0.20 → <0.15 → PRUNED
Auto-extract  → 0.30 → sunk → 0.15 → <0.15 → PRUNED
feedback(helpful)   → +0.15
feedback(unhelpful) → -0.15
```

---

## Troubleshooting & Diagnostics

### Health Check (One-Shot)

```bash
# Save as check_memory_health.py and run
python3 check_memory_health.py
```

Full script available in `references/health_check.py`.

### Failure Mode 1: "database is locked"

**Symptom**: MEMORY.md keeps growing, no "L0 sunk" in logs,
`Memory provider 'holographic' initialize failed: database is locked`
in journal.

**Root cause (two scenarios)**:

*Scenario A — Same-agent connection leak*: `initialize()` creates new
SQLite connections without closing old ones. Multiple session restarts
leak connections. When a leaked connection holds a write lock (uncommitted
transaction, WAL checkpoint), new connections get "database is locked" for 10+s.

*Scenario B — Inter-agent WAL race (gateway-specific)*: The gateway creates
a new AIAgent (with fresh MemoryStore) for every message. When the previous
agent's `shutdown()` calls `close()`, the WAL checkpoint is asynchronous —
the lock may still be held for 100-500ms. If the next agent's `initialize()`
fires immediately, MemoryStore creation hits the lock and fails.

**Fix (v2.5.1)**: 
- `initialize()` retries MemoryStore creation 3 times with 100ms/200ms delays
  → covers the WAL release window.
- `_enforce_l0_limit()` always runs (decoupled from DB) → MEMORY.md stays
  under limit even when all retries fail.
- `initialize()` and `shutdown()` close old connections before creating new ones
  (v2.5.0, already in place).

### Failure Mode 2: Facts exist but never retrieved

**Symptom**: 58 facts in fact_store, but searches for common terms return 0
results.

**Root cause**: FTS5 keyword search requires exact token matches. User says
"记忆机制", fact says "holographic memory protocol" — vocabulary mismatch.

**Fix (v2.5.0)**: TF-IDF semantic search replaces FTS5 as primary. Embedding
vectors are stored in `facts.embedding` column and loaded on startup.

### Failure Mode 3: Startup enforcement silently skipped (v2.5.1 FIXED)

**Symptom**: MEMORY.md > 2200 chars at session start with no "L0 sunk" log,
but no `database is locked` warning either. The file just keeps growing.

**Root cause (design flaw, not just DB issue)**: `initialize()` called
`_enforce_l0_limit()` AFTER `MemoryStore()` creation — same code block.
When MemoryStore creation threw ANY exception (not just "database is locked"),
the entire method exited before reaching the enforcement call. The
`MemoryManager.initialize_all()` caller caught and logged the exception,
but the sinking was silently skipped.

Under the gateway (where each new message creates a fresh AIAgent →
fresh MemoryStore), this created a race: previous agent's `shutdown()`
calls `close()` on its SQLite connection, but WAL checkpoint release is
asynchronous. If the new agent's `initialize()` fires before the WAL lock
clears, MemoryStore creation times out → exception → no sinking → MEMORY.md
grows unbounded over multiple sessions.

**Fix (v2.5.1)**: Two changes:
1. **Retry with backoff**: MemoryStore creation retries 3 times with
   100ms/200ms delays, giving WAL locks time to release.
2. **Decouple sinking from DB**: `_enforce_l0_limit()` now runs ALWAYS,
   before the exception is re-raised. It only needs filesystem access;
   `_mark_sunk()` gracefully returns when `self._store is None`.
   MEMORY.md never grows unbounded, even with a completely dead database.

**Verification**: Simulated complete DB failure (FakeStore that always
raises). MEMORY.md went from 3642 chars (15 entries, emergency tier) to
2428 chars (10 entries, sunk 5) — with `provider._store is None`.

**Key design principle**: L0 (hot memory, MEMORY.md) must NEVER depend on
L1 (warm memory, SQLite). They are independent layers — the hot layer
must remain operational even when the warm layer is unavailable.

---

## File Locations

The plugin code lives under `~/.hermes/hermes-agent/plugins/memory/holographic/`
(NOT `~/.hermes/plugins/`). The `hermes-agent` subdirectory contains the full
agent source code deployed alongside the config.

Key files:
- `__init__.py` — HolographicMemoryProvider, hooks, sinking
- `store.py` — MemoryStore, SQLite, embedding column
- `retrieval.py` — FactRetriever, semantic search pipeline
- `embedding.py` — TF-IDF vector index, tokenization, cosine similarity (NEW)
- `holographic.py` — HRR vector algebra (structural, not semantic)

---

## Pitfalls

- **Restart required**: All code patches need gateway/CLI restart.
- **Sequential path trap**: `run_agent.py` has TWO copies of the memory
  dispatch code. Both must have the `on_memory_write` bridge.
- **Connection leak → silent sinking failure**: Without the v2.5.0 fix,
  leaked connections hold write locks, `on_memory_write` fails, MEMORY.md
  grows unchecked. Always verify connection count after restart.
- **Single-process only**: `_enforce_l0_limit` writes MEMORY.md without fcntl
  lock. Multi-process deployments could race.
- **memory(action='replace')** triggers re-classification but NOT sinking.
- **auto_extract facts** at trust=0.30 are lower priority in semantic search.
- **Embedding backfill**: existing facts need `rebuild_embeddings()` run once
  after deploying v2.5.0. New facts auto-index on `add_fact()`.
- **Vocabulary growth**: each new fact with novel tokens extends the vector
  dimension. `rebuild_idf()` and `_restore_all_embeddings()` handle this
  automatically but add write overhead on first indexing.
- **Sinking priority**: when most entries share the same category, critical
  lessons get sunk alongside low-value tool configs. Future: weight
  \"lesson\"-tagged entries higher within their category tier.
- **Gateway per-message agent lifecycle**: gateway creates a new AIAgent
  (with fresh MemoryStore) for every message. `shutdown()` + `close()` +
  WAL checkpoint release is asynchronous → next agent may open before lock
  clears. v2.5.1 retry logic covers this, but be aware: any DB operation
  near agent startup is vulnerable to this race window.

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 2.5.1 | 2026-06-08 | **L0/DB decoupling**: `_enforce_l0_limit()` always runs in `initialize()`, even when MemoryStore creation fails. Retry logic (3× with backoff) survives transient WAL locks from inter-agent races. Hot layer (MEMORY.md) now operates independently of warm layer (SQLite). Fixed recurring \"database is locked → sinking silently skipped\" design flaw. |
| 2.4.0 | 2026-06-06 | Troubleshooting & Diagnostics: health check script, "database is locked" failure mode analysis, manual sinking procedure, startup enforcement gap documentation. |
| 2.3.0 | 2026-06-05 | Threshold recalibration: soft 1200→1600, warning 1600→1800, urgent 1800→2000, emergency 2000→2200. Skill renamed and reframed. Bilingual. |
| 2.2.2 | 2026-06-05 | Sequential path bridge: `_execute_tool_calls_sequential` missing `on_memory_write`. |
| 2.2.1 | 2026-06-05 | Startup enforcement: `_enforce_l0_limit()` in `initialize()`. |
| 2.2.0 | 2026-06-05 | on_session_finalize: auto_extract + prune. `_ProviderCollector.register_hook()`. |
| 2.1.0 | 2026-06-05 | Signal classification + tiered gradient sinking + `_mark_sunk`. |
| 2.0.0 | 2026-06-05 | Initial: on_memory_write mirror, trust-scored facts, FTS5+HRR. |
