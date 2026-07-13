# Agent Skills

A curated collection of installable skill protocols for AI agents — self-contained patches that extend agent capabilities. Drop in, reload, run.

## Skills

| Skill | Description |
|-------|-------------|
| [XuXiaoming-StockTradingStrategy](./XuXiaoming-StockTradingStrategy/) | 徐小明技术分析策略 **v4.6.11** — 蒸馏自「投资明见」2019-2026 2124篇文章。**两种模式**：盘后全流程（两路并行+合成+博客A20后置→九节报告）和盘中实时（Step-1四状态时间路由→七段简报）。**裁决层共振驱动**：主板五指数投票（上证/深证/创业板/沪深300/中证500）强→持股/空仓、混合→观望；科技双创共振（科创50定方向，双创共振→维持、分化→降档）。**钝化分析层**：日线结构引擎极值法20d + 分钟线极值法20d，bd/td双列拆分，90min顶钝化单信号转化率93-98%，底钝化⚠需结合日线。**8组规则**原文支撑，震荡框架闭环（上行出口76%/下行BS≥2→100%），21项反模式（A1-A21），独立数据中间层（build.py—键构建/verdict_v7.py共振裁决/breadth.py广度引擎/blog_monitor.py博客对照/realtime.py盘中裁决）。 |
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
