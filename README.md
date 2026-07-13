# Agent Skills

A curated collection of installable skill protocols for AI agents — self-contained patches that extend agent capabilities. Drop in, reload, run.

## Skills

| Skill | Description |
|-------|-------------|
| [XuXiaoming-StockTradingStrategy](./XuXiaoming-StockTradingStrategy/) | 徐小明技术分析策略 **v4.6.6** — 四层架构（能力层/表达层/规则层/工具接入层），蒸馏自「投资明见」2019-2026 2124篇文章。**两种模式**：盘后全流程（两路并行+合成+博客A20后置→九节报告）和盘中实时（Step-1四状态时间路由→七段简报）。**8组规则**全量原文支撑（R1趋势/R2 CHOP/R3结构/R4序列/R5共振/R6分钟线/R7双市场/R8个股分化），震荡全流程框架闭环（上行出口76%/下行BS≥2→100%），铁律推论固化（市况×结构对照表）。**9项默认工具**（三合一/CHOP/MACD结构/九转/分钟线四指数/五指数共振/NH-NL广度/博客对照/数据加载器），裁决出口5种。**20+反模式**（A1-A21含市况论证分列、博客三层隔离、模板强制检查清单）。独立数据中间层（build.py一键构建 + breadth.py广度引擎 + blog_monitor.py博客对照 + realtime.py盘中裁决）。封板测试212篇一致率66.5%（v17，A10修正）。 |
| [gaoshanwen-methodology](./gaoshanwen-methodology/) | 高善文·宏观分析思维方法论 v5.12 — 三层架构（能力层/操作层/表达层），D_fetch 数据中间层（23指标/三源合一），GAOBO 两遍制 + Loop 动态缺口清单（至多3轮）+ 重检强制 Checklist + 流水线规则，三种输出模式（演讲/研报/评论），正文/附录分离，比喻工具箱，历史案例库，跨国比较框架 |
| [Holographic Enhanced Memory Protocol](./holographic-enhanced-memory-protocol/) | **Mechanically enhanced edition** of Hermes-Agent's native holographic memory plugin. **Five core enhancements:** ① system-level enforced memory hooks (write/session/startup triple-anchor, agent cannot bypass) ② hot/warm/cold gradient memory system with tiered sinking and use-it-or-lose-it pruning ③ TF-IDF semantic retrieval replacing FTS5 keyword search (Chinese-aware tokenization, zero API calls) ④ radical lightness — all mechanical operations are code-driven, no new services or dependencies ⑤ L0/DB decoupling + comprehensive database lock fix (v2.5.2) — WAL pragma tuning, 10-retry backoff, clean checkpoint close, incremental embedding backfill. Hot layer operates independently of warm layer. Log-confirmed: 0 lock errors post-deploy. |

## Usage

```bash
# Clone into your skills directory
git clone git@github.com:Tadalafil-cure/agent-skills.git ~/.hermes/skills/agent-skills

# Or copy individual skills
cp -r agent-skills/holographic-enhanced-memory-protocol ~/.hermes/skills/
```

Then restart your agent. Skills are loaded at startup.

## Contributing

Each skill lives in its own directory with a `SKILL.md` file. PRs welcome.
