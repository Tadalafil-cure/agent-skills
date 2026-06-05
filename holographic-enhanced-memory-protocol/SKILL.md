---
name: holographic-enhanced-memory-protocol
description: "Hermes 原生 holographic 插件的机制增强版 — 系统级强约束记忆触发、热/温/冷三层梯度记忆、类脑记忆下沉与用进废退淘汰。零新依赖，同等轻量。 / A mechanically enhanced edition of Hermes' native holographic plugin — system-level enforced memory hooks, hot/warm/cold gradient memory, and brain-inspired memory sinking with use-it-or-lose-it pruning. Zero new dependencies."
version: 2.3.0
---

# Holographic Enhanced Memory Protocol

> *English version follows the Chinese below. 英文版在中文之后。*

**Hermes 原生 holographic 记忆插件的机制增强版。**

原生 holographic 给了积木：SQLite 结构化存储 + FTS5 全文检索 + 实体解析。
但它把「什么时候记、记什么、记多少」全部交给了 prompt 指令——软约束，Agent
可以跳过，也可以乱写。本协议在零新依赖的前提下，将软约束全部替换为挂钩系统
原生机制的硬约束，并引入热/温/冷三层梯度记忆模型。

---

**A mechanically enhanced edition of Hermes' native holographic memory plugin.**

The native holographic plugin provides the building blocks: SQLite structured
storage, FTS5 full-text search, and entity resolution. But it leaves *when to
remember, what to remember, and how much to keep* entirely to prompt
instructions — soft constraints the agent can skip or abuse. This protocol
replaces every soft constraint with hard hooks anchored in Hermes' native
mechanisms, and introduces a hot/warm/cold gradient memory model. Zero new
dependencies.

---

## 三项核心增强 · Three Core Enhancements

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
| L1 温记忆 · Warm | 🌤 可唤醒 Retrievable | 海马体结构化 · Hippocampal structured | SQLite + FTS5 | 信号分类 + 信任评分 + 按需检索 · Classified, trust-scored, on-demand |
| L2 冷记忆 · Cold | ❄ 归档 Archived | 皮层情景记忆 · Cortical episodic | session_search | 完整对话原文，手动回溯 · Raw transcripts, manual recall |

**记忆下沉不是删除，是降级**——就像人脑不会真正「忘记」，只是从活跃意识退到
深层存储。下沉到 L1 的事实仍然可检索，只是信任分降低、不再常驻上下文。
多次不被唤醒的事实持续衰减，直到被自动清理——这是「用进废退」的工程实现。

**Sinking is degradation, not deletion.** Just as the human brain doesn't truly
"forget" — it merely demotes from active awareness to deeper storage. Sunk facts
remain retrievable in L1, just at reduced trust and no longer resident in
context. Facts that go unrecalled decay continuously until automatic pruning —
an engineering realization of *"use it or lose it."*

### 三、极致轻量
### Ⅲ. Radical Lightness

本协议没有引入任何新服务、新数据库、新依赖。全部增强都发生在 holographic
插件已有的 SQLite + FTS5 + 文件系统之上。分类是正则，下沉是文件读写，评分
是计数器——所有机械操作由代码完成，不消耗 LLM token。适合离线环境、单机
部署、嵌入式设备。

*This protocol introduces zero new services, databases, or dependencies. Every
enhancement runs on holographic's existing SQLite + FTS5 + filesystem stack.
Classification is regex. Sinking is file I/O. Scoring is counters. All
mechanical operations are code-driven — zero LLM token cost. Suitable for
offline environments, single-machine deployments, and embedded devices.*

---

## Quick Start

Apply these patches to a fresh Hermes Agent installation, then restart.
The protocol lives in two files — one for the holographic plugin, one to
bridge a missing hook path in the agent loop.

### Patch 1: Holographic Plugin

**File**: `plugins/memory/holographic/__init__.py`

#### 1a. Add signal classification + tiered sinking + post-sink tagging

Before the `class HolographicMemoryProvider` line, insert the signal map,
classifier, and L0 limit constants. If these don't exist, add them; if older
versions exist, replace.

```
# Insert after the imports, before the FACT_STORE_SCHEMA definition:

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

#### 1b. Add startup enforcement

In `initialize()`, after `self._session_id = session_id`, add:

```python
        self._session_id = session_id
        # Enforce L0 limits on startup — MEMORY.md may exceed limits
        # from writes that happened before this code was deployed.
        self._enforce_l0_limit()
```

#### 1c. Add on_memory_write with classification + sinking

If `on_memory_write` exists but only does mirroring, replace it. If it doesn't
exist, add it to `HolographicMemoryProvider`:

```python
    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if action not in ("add", "replace") or not self._store or not content:
            return
        try:
            category, tags = _classify_signal(content)
            self._store.add_fact(content, category=category, tags=tags)
            if target == "memory":
                self._enforce_l0_limit()
        except Exception as e:
            logger.warning("Holographic memory_write failed: %s", e)
```

#### 1d. Add _enforce_l0_limit (tiered sinking)

Add to `HolographicMemoryProvider`:

```python
    def _enforce_l0_limit(self, soft_limit=_L0_SOFT_LIMIT,
                          emergency_limit=_L0_EMERGENCY_LIMIT) -> None:
        from hermes_constants import get_hermes_home
        mem_path = get_hermes_home() / "memories" / "MEMORY.md"
        if not mem_path.exists():
            return
        try:
            raw = mem_path.read_text(encoding="utf-8")
        except Exception:
            return
        size = len(raw)
        if size <= soft_limit:
            return
        entries = [e.strip() for e in raw.split(_MEMORY_ENTRY_DELIMITER) if e.strip()]
        if len(entries) <= 1:
            return
        # Tiered sink count: graduated thresholds
        # 1600+ gentle, 1800+ warning, 2000+ urgent, 2200+ emergency
        if size > 2200:
            sink_count = min(5, len(entries) - 1)
            tier = "emergency"
        elif size > 2000:
            sink_count = min(3, len(entries) - 1)
            tier = "urgent"
        elif size > 1800:
            sink_count = min(2, len(entries) - 1)
            tier = "warning"
        else:
            sink_count = 1
            tier = "gentle"
        scored = []
        for idx, entry in enumerate(entries):
            cat, _ = _classify_signal(entry)
            priority = _CATEGORY_PRIORITY.get(cat, 0)
            scored.append((priority, idx, entry))
        scored.sort(key=lambda x: (x[0], x[1]))
        victims = {scored[i][2] for i in range(min(sink_count, len(scored)))}
        kept = [e for e in entries if e not in victims]
        try:
            mem_path.write_text(
                _MEMORY_ENTRY_DELIMITER.join(kept) + "\n",
                encoding="utf-8",
            )
            logger.info("L0 sunk %d entries → %d chars (was %d, tier=%s)",
                        len(victims), len(_MEMORY_ENTRY_DELIMITER.join(kept)),
                        size, tier)
        except Exception as e:
            logger.warning("L0 sink rewrite failed: %s", e)
        for victim in victims:
            self._mark_sunk(victim)
```

#### 1e. Add _mark_sunk

```python
    def _mark_sunk(self, content: str) -> None:
        if not self._store:
            return
        try:
            row = self._store._conn.execute(
                "SELECT fact_id, tags, trust_score FROM facts WHERE content = ?",
                (content,),
            ).fetchone()
            if not row:
                return
            fact_id, existing_tags, current_trust = row
            tag_set = {t.strip() for t in (existing_tags or "").split(",") if t.strip()}
            if "sunk" in tag_set:
                return
            tag_set.add("sunk")
            new_tags = ",".join(sorted(tag_set))
            new_trust = max(0.2, current_trust - 0.15)
            self._store._conn.execute(
                "UPDATE facts SET tags = ?, trust_score = ? WHERE fact_id = ?",
                (new_tags, new_trust, fact_id),
            )
            self._store._conn.commit()
        except Exception as e:
            logger.warning("_mark_sunk failed: %s", e)
```

#### 1f. Upgrade silent exception handlers

Find every `logger.debug` inside exception handlers in these methods and
change to `logger.warning`:

- `on_memory_write` except block
- `_enforce_l0_limit` write_text except block
- `_mark_sunk` except block

#### 1g. Add _prune_low_trust (if not present)

```python
    def _prune_low_trust(self, max_facts=200, cull_trust=0.15) -> None:
        if not self._store:
            return
        try:
            conn = self._store._conn
            cur = conn.execute("DELETE FROM facts WHERE trust_score < ?", (cull_trust,))
            hard_deleted = cur.rowcount
            total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            if total > max_facts:
                excess = total - max_facts
                conn.execute(
                    """DELETE FROM facts WHERE fact_id IN (
                        SELECT fact_id FROM facts
                        ORDER BY CASE WHEN tags LIKE '%sunk%' THEN 0 ELSE 1 END,
                                 trust_score ASC LIMIT ?
                    )""", (excess,))
                soft_deleted = conn.rowcount
                conn.commit()
                logger.info("Pruned %d facts (hard=%d soft=%d, kept=%d)",
                            hard_deleted + soft_deleted, hard_deleted,
                            soft_deleted, total - hard_deleted - soft_deleted)
            elif hard_deleted > 0:
                conn.commit()
                logger.info("Pruned %d abandoned facts", hard_deleted)
        except Exception as e:
            logger.debug("_prune_low_trust failed: %s", e)
```

#### 1h. Add on_session_finalize hook handler

```python
    def on_session_finalize(self, **kwargs) -> None:
        session_id = kwargs.get("session_id")
        if not session_id:
            return
        messages = []
        try:
            from hermes_constants import get_hermes_home
            from hermes_state import SessionDB
            db_path = get_hermes_home() / "state.db"
            if db_path.exists():
                sdb = SessionDB(db_path)
                messages = sdb.get_messages_as_conversation(session_id)
                sdb.close()
        except Exception as exc:
            logger.debug("on_session_finalize: cannot load messages: %s", exc)
        if self._config.get("auto_extract", False):
            if self._store and messages:
                self._auto_extract_facts(messages)
        self._prune_low_trust()
```

#### 1i. Update register() function

```python
def register(ctx) -> None:
    config = _load_plugin_config()
    provider = HolographicMemoryProvider(config=config)
    ctx.register_memory_provider(provider)
    ctx.register_hook("on_session_finalize", provider.on_session_finalize)
```

#### 1j. Ensure _ProviderCollector forwards hooks

In `plugins/memory/__init__.py`, the `_ProviderCollector.register_hook` method
must forward to the real PluginManager. If it's a no-op, replace with:

```python
    def register_hook(self, hook_name: str, callback) -> None:
        try:
            from hermes_cli.plugins import get_plugin_manager
            get_plugin_manager()._hooks.setdefault(hook_name, []).append(callback)
        except Exception:
            pass
```

---

### Patch 2: Run Agent (Sequential Path Bridge)

**File**: `run_agent.py`

**Critical**: `run_agent.py` has TWO copies of the memory tool dispatch code.
Only `_invoke_tool` (used by parallel tool execution) has the `on_memory_write`
bridge. `_execute_tool_calls_sequential` (used by single tool calls — the
default on WeChat, Telegram, and CLI) is missing it.

Find the `elif function_name == "memory":` block inside
`_execute_tool_calls_sequential` and add the bridge after `_memory_tool(...)`:

```python
            elif function_name == "memory":
                target = function_args.get("target", "memory")
                from tools.memory_tool import memory_tool as _memory_tool
                function_result = _memory_tool(
                    action=function_args.get("action"),
                    target=target,
                    content=function_args.get("content"),
                    old_text=function_args.get("old_text"),
                    store=self._memory_store,
                )
                # Bridge: notify external memory provider
                if self._memory_manager and function_args.get("action") in ("add", "replace"):
                    try:
                        self._memory_manager.on_memory_write(
                            function_args.get("action", ""),
                            target,
                            function_args.get("content", ""),
                        )
                    except Exception:
                        pass
                tool_duration = time.time() - tool_start_time
```

---

## Verification

After patching and restarting:

```bash
# 1. Check log for successful registration
grep 'holographic.*registered' ~/.hermes/logs/agent.log | tail -1

# 2. In a chat, send a memory write via the agent:
#    "Remember: I prefer dark mode"

# 3. Check fact_store mirroring
sqlite3 ~/.hermes/memory_store.db "SELECT fact_id, category, tags FROM facts ORDER BY fact_id DESC LIMIT 3;"

# 4. Check sinking — push MEMORY.md past 1600 chars with several writes,
#    then verify a "L0 sunk" log entry appears:
grep 'L0 sunk' ~/.hermes/logs/agent.log | tail -3
```

---

## Architecture Reference

### Data Flow

```
Agent calls memory(action='add', content='...')
  │
  ├── _memory_tool() writes MEMORY.md (L0)
  │
  └── on_memory_write() HOOK (unskippable)
        ├── _classify_signal(content) → (category, tags)
        ├── fact_store.add() → L1 mirror
  └── _enforce_l0_limit()
              ├── 1600+ chars → gentle   (sink 1)
              ├── 1800+ chars → warning  (sink 2)
              ├── 2000+ chars → urgent   (sink 3)
              └── 2200+ chars → emergency (sink 5)
                    └── _mark_sunk(victim)
                          ├── tag += "sunk"
                          └── trust -= 0.15

Session start:
  initialize() → _enforce_l0_limit()  ← startup safety net

Session end (/new, /reset, timeout):
  on_session_finalize()
    ├── auto_extract_facts(messages) → trust=0.30
    └── _prune_low_trust() → cull <0.15, cap 200
```

### Layers

| Layer | Temperature | Cognitive Analog | Storage | Mechanism |
|-------|------------|-----------------|---------|-----------|
| L0 热记忆 · Hot | 🔥 Active | Prefrontal working | MEMORY.md | Full injection; gradient sink when >1600 chars |
| L1 温记忆 · Warm | 🌤 Retrievable | Hippocampal structured | SQLite + FTS5 + HRR | Signal-classified, trust-scored, per-turn prefetch |
| L2 冷记忆 · Cold | ❄ Archived | Cortical episodic | SQLite sessions | Raw transcripts, manual recall |

Sinking is degradation, not deletion. Sunk facts remain retrievable in L1 at reduced
trust. The trust scoring system models "use it or lose it" — frequently recalled
facts rise; abandoned facts decay to automatic pruning.

### Trust Lifecycle

```
Active save   → 0.50 → sunk → 0.35 → sunk again → 0.20 → <0.15 → PRUNED
Auto-extract  → 0.30 → sunk → 0.15 → <0.15 → PRUNED
feedback(helpful)   → +0.15
feedback(unhelpful) → -0.15
```

---

## Pitfalls

- **Restart required**: All code patches need a gateway/CLI restart. Python
  modules are cached in memory — file edits don't take effect until reload.
- **Sequential path trap**: `run_agent.py` has TWO copies of the memory
  dispatch code (`_invoke_tool` for parallel, `_execute_tool_calls_sequential`
  for single calls). Any new bridge/hook added to one MUST be added to the
  other. This is the #1 reason hooks silently fail on WeChat/Telegram/CLI.
- `_enforce_l0_limit` writes MEMORY.md without fcntl lock. Safe in
  single-process deployments; multi-process setups could race.
- `memory(action='replace')` triggers re-classification but NOT sinking
  (doesn't change L0 size).
- auto_extract facts at trust=0.30 are invisible to prefetch when
  higher-trust facts match the same query.
- YAML indent: plugin children must be indented 6 spaces, not 4. Verify
  with a parse check after editing `plugin.yaml`.

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 2.3.0 | 2026-06-05 | **Threshold recalibration**: soft 1200→1600, warning 1600→1800, urgent 1800→2000, emergency 2000→2200, hard cap 3000→2600. Tier logic changed from percentages to hardcoded values. Skill renamed and reframed around three enhancements: system-level enforcement, hot/warm/cold gradient memory, and radical lightness. Bilingual (zh/en). |
| 2.2.2 | 2026-06-05 | **Sequential path bridge**: `_execute_tool_calls_sequential` was missing `on_memory_write`. Added bridge. |
| 2.2.1 | 2026-06-05 | **Startup enforcement**: `_enforce_l0_limit()` in `initialize()`. Upgraded silent `logger.debug` → `logger.warning`. |
| 2.2.0 | 2026-06-05 | **on_session_finalize**: auto_extract + prune fire on session boundaries. `_ProviderCollector.register_hook()` bridge. |
| 2.1.0 | 2026-06-05 | Signal classification + tiered gradient sinking + `_mark_sunk`. |
| 2.0.0 | 2026-06-05 | Initial: on_memory_write mirror, trust-scored facts, FTS5+HRR. |
