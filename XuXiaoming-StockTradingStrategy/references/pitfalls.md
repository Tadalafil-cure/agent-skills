# 已知陷阱速查

## P1：INDEX_MAP 扩容后双处硬编码不同步（v4.6.6 发现）

**症状：** 分钟线引擎明明生成了四指数 CSV，但盘中简报只显示上证深证。

**根因：** INDEX_MAP 从 `{sh, sz}` 扩容到 `{sh, sz, cyb, kc}` 时，有两个地方各漏了一处硬编码：

| 位置 | 硬编码 | 修复 |
|------|------|------|
| `scripts/minute_structure_v2.py:221` | `for idx in ["sh", "sz"]:` | → `for idx in INDEX_MAP:` |
| `data_layer/realtime.py:445` | `for idx_code, idx_name in [("sh","上证"), ("sz","深证")]:` | → 加 cyb 和 kc |

**教训：** 任何数据源扩容（INDEX_MAP、INDICES_SINA 等），必须全文搜索该变量的引用，检查是否有独立维护的硬编码副本。两处不同步 = 数据生成了但不消费 = 静默丢失。

## P9：blog_monitor 子 Agent 误报"无对应文章"（2026-07-20 发现）

**症状：** 子 Agent 调用 `blog_monitor.py --date 2026-07-20` 后返回"无对应操作策略文章"，但手工重跑发现有文章（《周二操作策略》，当日发布）。

**根因：** 子 Agent 的独立上下文中可能因网络波动、blog_monitor 缓存或其他环境差异导致查询失败。子 Agent 返回的结果是自报告的，不可全信。

**防护：**
- 子 Agent 返回"无文章"时，主 Agent 应手工验证：`python scripts/blog_monitor.py --date YYYY-MM-DD`
- 尤其是周一~周四的分析日——这些日期的文章通常前一天收盘后发布，不易缺失
- 周五特殊情况（查周一策略）允许"未上线"为正常结果

## P10：build.py 午夜运行生成虚假次日数据（2026-07-20 发现）

**症状：** 系统时间 00:37（次日凌晨），build.py 拉取的数据中出现了次日（7/21）的行，但 close 值与前一天（7/20）完全相同。CHOP 因同值重算产生变化。Agent 误以为 7/21 数据已出，提前判断"退震确认"。

**根因：** akshare 在凌晨时可能返回占位行（次日日期+前日收盘价），process.py/verdict_v7.py 照常处理后生成"假数据"。

**防护：**
- 分析前检查最新日期的 close 是否与前一天不同——相同则说明是占位行，丢弃
- 报告生成前强制运行 `date "+%Y-%m-%d %A %H:%M"` 确认当前时间
- 午夜前后（23:00-09:00）生成的报告需标注"数据可能为前日收盘"

## P2：分钟线 CSV 列名假设（已修，见 A21 反模式）

`minute_structure_v2_{sh,sz,cyb,kc}.csv` 的列名不是 `60min_signal`/`90min_signal`，而是 `top_form_60`/`bottom_form_60`/`bd_60`/`td_60`/`signal_level` 等。v4.6.11 起 diverge 单列已拆为 bd(底钝化)/td(顶钝化)。用错列名→全空→静默填「无结构」。

## P3：structure_signals.csv 格式假设（已修，见 A17 反模式）

长格式（index_name + bottom/top_structure）≠ 宽格式（bs_sh/ts_sh...）。直接对长格式文件查宽格式列名→pandas 不报错返回空列→Agent 假设"零结构"。

## P4：realtime.py 时间检测（v4.6.6 强化）

简报标题行必须显式标注星期（周一/周二），防止 Agent 或用户产生"今天是周几"的幻觉。已通过 `weekday_cn` 变量实现。

## P5：补跑全流程 ≠ 只跑 verdict_v7.py

`ensure_verdict_fresh()` 只保证 CSV 数据就绪。前日完整报告需要九节（含 A19 分列、共振轨迹、NH/NL 详述、四指数分钟线），必须走两路并行+合成+博客后置全流程。不可用"verdict CSV 已就绪"替代"报告已就绪"。

## P6：绕过管线直接做临时分析（2026-07-14 实战纠正）

**症状：** Agent 用实时 API（Tencent/Sina 接口）拿到当日收盘数据后，直接手工写一份"徐小明风格"报告——不跑 build.py / verdict_v7 / minute_structure / breadth / blog_monitor 任何一步。

**为什么致命：**
- 手工分析没有裁决引擎的结构信号（bs/ts）、钝化状态（bd/td）、CHOP 分档、共振投票——只是在"模仿语气"
- 没有分钟线结构 → 缺少 M1/M2 修边依据
- 没有博客对照 → 没有第九节独立验证（A20 隔离必要）
- 没有广度数据 → 无法判断 R8 叠加低位和 NH/NL 状态
- 没有全量历史数据 → 市况判断（H17 来路检测/CHOP 轨迹/振荡来路）完全基于猜测
- 用户纠正原话："**你这个不是按照我的全流程做的**"

**正确做法：**
1. Step -1：market_status() 日期校验
2. Step 0：`python data_layer/build.py` 全量构建
3. Step 1：verdict_v7 + minute_structure + breadth
4. Step 2-3：主 Agent 一~八节 + 博客 Agent 九节（A20 隔离）
5. **绝不走"已有实时数据→直接分析"的捷径**

**检查清单：** 报告产出前确认以下文件均为当日最新：
- `data/verdict_v7.csv`（裁决引擎）
- `data/minute_structure_v2_*.csv`（四指数分钟线）
- `data/breadth_daily.csv`（NH/NL 广度）
- `data/structure_signals.csv`（日线结构）
- `data/turn_sequence_events.csv`（九转序列）

## P7：震荡来路判断——BS≥2 常见误解（v4.6.24 更新：BS≥2已降级为推论S4）

**症状：** 把 BS≥2 解释为「两个指数同一天形成底结构」，或把下行震荡规则（BS 累计次数）套用到上行震荡。

**v4.6.24 正确规则：**
- 规则层：震荡中⛔不操作——跟来路无关。等出口方向或趋势突破（H17/R3.3）
- 推论层 S4：下行来路震荡 BS≥2→试探（回测信号，非操作规则）
- 推论层 S5：震荡中 BS 筛选参数（dd>15%/8%等，回测校准）
- H17b（特别提示）：上行来路已减仓→震荡中底结构不触发

**⚠️ 以下为 v4.5.6/v4.6.23 旧规则，已废弃，仅留作历史参考：**

```
第一步：定来路
  来路 = 震荡前最后一个 ≥7 天的趋势段方向

第二步：选规则（v4.6.23 ⚠️ v4.5.6旧规则已废弃）

  ⛔ 以下为v4.5.6旧规则，已在v4.6.23中替换。新框架：入震≥2d→退震分流(上行≥3d/下行≥4d)→方向+CHOP操作。
  详见 references/upward-origin-oscillation-model.md 和 references/downward-origin-oscillation-model.md。

  （以下为历史参考，不可直接使用）
  上行来的震荡 → 出口方向规则
    ├── 出口偏多/上行趋势 → 看多（76% 正确）⚠️ v7下仅41%
    └── 出口偏空/下行趋势 → 观望（65% 会跌）⚠️ v7下不成立

  下行来的震荡 → BS 累计次数规则
    ├── BS≥2 → 试探入场（走强率 100%）⚠️ v4.6.23改为退震确认后跟方向
    │     └── BS 指【本轮震荡累计底结构次数】，不是同一天几个指数
    ├── BS=1 → 不入场（走强率 38%，假底陷阱）
    └── BS=0 → 不判断（走强率 52%，抛硬币）
```

**三个常见错误：**

| 错误 | 正确 |
|------|------|
| BS≥2 = 两个指数同一天出底结构 | BS≥2 = 同一段震荡累计 ≥2 次底结构 |
| 上行震荡也等 BS≥2 | 上行看出口方向，不看 BS |
| BS≥2 = 震荡结束信号 | BS≥2 = 试探入场信号，入场后还要等偏多出口加满/偏空出口止损 |

**防护：震荡期间的报告模板 v1.11 已强制包含来路判断三段链路（来路→选规则→当前链路状态），必须逐项填写，不可跳过。**

## P8：skill_manage + agent-skills 路径（见 fact-102）

skill_manage 对 agent-skills 路径下的 skill（非 `~/.hermes/skills/` 软链目标）返回 "not found in active profile default"。需通过 patch 直写物理路径。
