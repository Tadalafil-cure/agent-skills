# a-share-analyst Skill · 实施规划文档

> 版本：v1.0 | 状态：规划中 | 最后更新：2026-06-15
> 位置：`~/.hermes/skills/a-share-analyst/`
> 基于 6 份外部 skill 分析 + 10 盲区补齐的完整设计方案

---

## 目录

1. [架构总览](#一架构总览)
2. [Agent 团队规格](#二agent-团队规格)
3. [数据层：中间层对接与补齐](#三数据层中间层对接与补齐)
4. [计算层：10 脚本清单](#四计算层10-脚本清单)
5. [执行流程与时序](#五执行流程与时序)
6. [文件清单](#六文件清单)
7. [实施阶段](#七实施阶段)
8. [风险与约束](#八风险与约束)

---

## 一、架构总览

### 1.1 三层分离 + 数据纪律

```
┌─────────────────────────────────────────────────────────────┐
│  数据层 (Main Agent Step 0)                                  │
│  中间层函数 → data_package (JSON)                            │
│  纯机械，无推理。耗时 ~10-15s                                │
│  ═══════════════════════════════════════════════════════════ │
│  ⛔ 数据防火墙：此处是唯一合法数据入口                         │
│  子 Agent 禁止自行拉数。数据不够 → 标注而非编造              │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  计算层 (子 Agent terminal 调用)                             │
│  10 个 Python 脚本：ta / scorer / signal / validator /      │
│  multi_tf / risk_quant / earnings_surprise / rotation /     │
│  theme_detector / screener                                  │
│  确定性计算，零 LLM 参与。单脚本耗时 1-5s                     │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  推理层 (8 个子 Agent，delegate_task 派发)                   │
│  每个 Agent 独立上下文、独立推理、独立产出报告                │
│  LLM 只做推理：解读指标、判断逻辑、撰写报告                   │
│  超时：900s/Agent                                            │
│  ⛔ 禁止调 akshare/web_search/web_fetch/中间层函数            │
│  数据来源只有 context 中的 data_package 子集                  │
└─────────────────────────────────────────────────────────────┘
```

### 1.1a 数据纪律（Data Discipline）— 系统级硬约束

```
                    Step 0: 主 Agent 批量拉数
                    data_package = { market, stock, financial, macro }
                              │
          ┌───────────────────┼───────────────────┐
          ↓                   ↓                   ↓
     Agent A context     Agent B context     Agent C context
     {market子集}         {financial子集}     {stock子集}
          │                   │                   │
          ⛔                    ⛔                   ⛔
     禁止自行拉数          禁止自行拉数         禁止自行拉数

规则：
1. data_package 是子 Agent 获取数据的唯一来源
2. 子 Agent 不可调用任何数据获取函数（中间层/akshare/web_*）  
3. 脚本（ta.py/scorer.py等）从 data_package 的 JSON 读输入，不自行拉数
4. 如 data_package 中缺少必需数据 → 在报告中标注「数据不足：缺少XXX」
   → 不编造、不绕过、不降级获取
5. 主 Agent Step 0 是系统中唯一执行数据采集的实体
```

**预留例外**（当前不启用，将来按需开放）：

某些分析维度可能需要实时外部数据，不在 data_package 预采集范围内——例如社区情绪（雪球/股吧讨论）、突发新闻、实时的舆情变化。这类数据：
- 目前一律走「数据不足」标注
- 将来如需开放，按例外流程：明确限定模块 → 限定数据类型 → 限定获取方式 → 记录在案
- 不在当前 Phase 0-3 实施范围内

**用户外部输入通道**（分析原点，非数据替代）：

用户调用此 skill 时，除股票代码外，可能附带外部信息——分析师报告摘要、研究笔记、网络流传信息、特定逻辑推演等。

这类信息的性质：
- 是分析的**原点**——可能包含一个投资逻辑、一个预期差假设、一个新的观察角度
- **不是**对中间层数据的替代或覆盖——准确度未必高于 API 数据
- 核心价值在于「市场在讨论什么逻辑」和「数据能不能验证这个逻辑」
- 可能正是**预期差的来源**——市场叙事 vs 实际数据的偏差

处理方式：
- Step 0 将用户输入放入 `data_package.user_input`，注入到全部 8 个子 Agent 的 context
- 各 Agent 的角色不是「相信外部信息」，而是「用自己领域的数据去验证或挑战其中的论断」
- 例如：用户输入提到「公司业绩超预期」，Agent B 用实际财务数据对照；提到「技术面金叉」，Agent C 跑 ta.py 独立验证
- 外部输入与脚本/数据结论的**分歧本身也是分析产出**——标注为「市场逻辑 vs 数据现实」的对照
- 空字符串 = 无外部输入，正常走全自动流程

```python
# data_package 结构扩展
data_package = {
    "symbol": "600519",
    "user_input": "用户提供的额外文字信息（可为空字符串）",
    "market": {...},
    "stock": {...},
    "financial": {...},
    "macro": {...},
}
```

**为什么这样做**：

| 问题 | 如果子 Agent 各自拉数 | 我们的方案 |
|------|---------------------|-----------|
| 重复拉取 | 8 个 Agent 可能重复调用同一函数 8 次 | 1 次采集，8 次分发 |
| token 浪费 | 每次函数调用结果进入子 Agent 上下文 | 仅在 Step 0 进入一次 |
| 数据不一致 | 不同时间拉取可能得到不同快照 | 同一快照，全团队基于同一数据辩论 |
| 调试困难 | 不知道哪个 Agent 从哪拉了数据 | 数据来源可追溯——都在 data_package 里 |
| 幻觉风险 | Agent 可能"顺手"调个 web_search | 物理隔离：子 Agent 无 web/search 工具 |

### 1.2 六家继承与十盲区补齐

| 能力维度 | 继承来源 | 盲区 | 补齐方案 |
|---------|---------|------|---------|
| 主线识别 | Wind 6步 | 无时间序列 | `rotation.py` + 20日板块历史 |
| 技术分析 | geek ta.py + cn-stock 规则表 | 单周期 | `multi_tf.py` 五周期共振 |
| 择时评分 | biga 四维打分 | 无历史验证 | `validator.py` 动态置信度 |
| 信号决策 | biga 三信号交叉 | 静态阈值 | 历史胜率驱动的动态决策 |
| 基本面 | chris3cano 选股 + cn-stock 估值 | 无预期差 | `earnings_surprise.py` + 产业链 |
| 资金博弈 | chris3cano 第三步 | 无机构追踪 | 机构持仓变化 + 可转债 |
| 风控 | biga ATR止损 | 单指标 | Agent H 纠偏 + risk_quant.py |
| 宏观 | — (六家都缺) | 全缺 | Agent G + `get_macro_indicators()` |
| 架构 | niuniu 代码驱动 | 单线程 | 8 Agent 并行协作 |
| 质控 | — (六家都缺) | 无交叉验证 | Agent F 矛盾检测 + 盲区标注 |

---

## 二、Agent 团队规格

### 2.1 超时与资源

| 参数 | 值 | 说明 |
|------|-----|------|
| **每个子 Agent 超时** | **900s (15分钟)** | `delegate_task` 的 `max_iterations` 不做硬限制，靠超时兜底 |
| 最大并行数 | 3 | `delegate_task` batch 模式硬限制 |
| 推理强度 | `reasoning_effort="high"` | 所有子 Agent 统一使用，保证分析深度 |
| 工具集 | `["terminal", "file"]` | 所有子 Agent 统一。不需要 web/search，数据来自 context |
| 上下文注入 | data_package 子集 + agent brief | 不注入无关数据，保持上下文精炼 |

### 2.2 团队编制（13 Agent · 辩论架构）

核心变化：基本面和技术面从单 Agent 分析升级为**对立视角辩论 + 独立裁判**模式。同一组数据，正反双方全力论证各自的立场，裁判在完整听取双方论据后裁决。避免单 Agent "左右互搏"导致的结论模糊。

#### Phase 1 — 3 并行（基本面辩论 + 市场分析）

**Agent B1：多头分析师** 🆕
```
角色：基本面多头辩护律师
原则：从财务数据中全力挖掘看多证据。不看空，不中和，不 hedge
输入：data_package.financial (财务三表/杜邦/成长/估值/预测/概况)
      data_package.stock (估值对比/规模对比/公司概况)
脚本：scorer.py --mode fundamental（计算结果作为论据，不打分时隐去得分）
输出：fundamental_bull.md (~800-1200字)
  【1.核心看多逻辑】(一句话)
  【2.盈利能力】(ROE/毛利率/净利率，每条标注数据来源)
  【3.成长性】(历史增速+预测增速+行业对比)
  【4.估值优势】(PE/PB 行业中值对比，如不低则说"估值合理，非减分项")
  【5.护城河】(品牌/技术/规模/网络/特许)
  【6.催化剂】(即将发生什么能让股价涨？)
  【7.多头评分】(1-5星，基于论据强度)
硬约束：
  - 必须基于 data_package 中的财务数据，每条论据标注来源
  - 如果某个维度确实找不到看多证据，标注"本维度无看多证据"而非强行找
  - 不引用基本面对手(B2)的观点，不预判反方论据
预估耗时：60-180s
```

**Agent B2：空头分析师** 🆕
```
角色：基本面空头辩护律师
原则：从财务数据中全力挖掘看空证据。不看多，不中和，不 hedge
输入：与 B1 完全相同（同一份数据，对立解读）
脚本：scorer.py --mode fundamental
输出：fundamental_bear.md (~800-1200字)
  【1.核心看空逻辑】(一句话)
  【2.盈利能力缺陷】(任何下滑/恶化/低于行业的指标)
  【3.成长性风险】(增速放缓/预测下调/行业天花板)
  【4.估值压力】(高估指标+行业中值对比，如不贵则说"估值非看空理由")
  【5.护城河裂痕】(竞争侵蚀/技术替代/客户流失)
  【6.风险事件】(即将发生什么能让股价跌？)
  【7.空头评分】(1-5星，基于论据强度)
硬约束：
  - 与 B1 完全相同的硬约束，方向相反
  - PE为负→重点论证"公司亏损本身就是核心风险"
  - 盈利预测null→标注"无机构覆盖，市场缺乏共识"
预估耗时：60-180s
```

**Agent A：市场策略师**
```
角色：A股市场结构研究员（15年经验）
继承：Wind 6步主线 + biga 择时分
增强：板块轮动时间序列(rotation.py)
输入：data_package.market (指数/宽度/行业/概念/北向/两融/20日板块历史)
脚本：theme_detector.py, rotation.py
输出：market_report.md (~1500-2500字)
  【1.市场环境】【2.当前主线】【3.次级热点】【4.核心锚点】
  【5.情绪周期】【6.轮动追踪】【7.持续性评估】【8.明日观察】
预估耗时：60-180s
```

#### Phase 1b — 3 并行（基本面裁判 + 技术辩论启动）

**Agent B3：基本面综合裁判** 🆕
```
角色：基本面首席分析师——基于 B1/B2 的辩论，做最终裁决
原则：不看原始数据（B1/B2 已看过），只看双方的论据质量
      裁判的核心问题是：哪一方的论据更基于数据、更少主观臆断？
输入：B1 报告全文 + B2 报告全文 + data_package.financial (仅用于事实核查)
脚本：无 (纯裁决推理)
输出：fundamental_judge.md (~1000-1500字)
  【1.论据对比】B1 vs B2 在各维度的论据对照表
  【2.论据质量评估】哪方论据更硬？哪些论据数据支撑不足？
  【3.核心分歧】双方最大的分歧点在哪？能裁决吗？
  【4.财务×技术预判】基本面结论对技术面的含义（供 C1/C2 参考）
  【5.最终评级】🟢买入 / 🟡中性 / 🔴回避 + 1-5星确信度
  【6.裁决依据】(3条以内核心原因)
  【7.确信度证据】🆕 (供后续自循环复盘)
    • 正反双方论据数量比（B1论据数 : B2论据数）
    • 核心分歧是否可裁决？（可裁决=数据清晰支持一方 / 不可裁决=双方论据质量相当）
    • 裁决依赖的关键假设（如假设失效，评级是否翻转？）
预估耗时：90-240s
```

**Agent C1：趋势派技术分析师** 🆕
```
角色：趋势跟随交易员
原则：顺势而为。只看趋势信号，不看超买超卖
      核心假设：趋势一旦形成，更可能延续而非反转
输入：data_package.stock (日K线≥120日+周K线+60min/30min+实时行情)
脚本：ta.py, multi_tf.py, scorer.py --mode technical（侧重趋势维度）
输出：trend_bull.md (~800-1200字)
  【1.多周期趋势一致性】(周线/日线/60min 的趋势方向是否一致？)
  【2.均线系统】(多头/空头/交叉排列，MA排列强度)
  【3.MACD 趋势信号】(DIFF方向/零轴位置/柱状图趋势，不含背离)
  【4.ADX/趋势强度】(如有)
  【5.成交量趋势】(量价配合还是背离？)
  【6.趋势支撑/阻力】(关键价位，基于趋势线/均线/前高前低)
  【7.趋势派评分】(1-5星)
  【8.触发条件】🆕
    • 顺势做多触发价（突破哪个价位确认趋势延续？）
    • 趋势失效条件（跌破哪个价位趋势改变？）
硬约束：
  - 不分析 RSI 超买超卖（那是 C2 的领域）
  - 不分析底背离/顶背离（那是 C2 的领域）
  - 不分析布林带收窄突破（那是 C2 的领域）
预估耗时：60-180s
```

**Agent C2：反转派技术分析师** 🆕
```
角色：均值回归交易员
原则：极端之后必回归。只看反转信号，不看趋势
      核心假设：超买会回调，超卖会反弹，背离预示反转
输入：与 C1 完全相同（同一份数据，对立解读）
脚本：ta.py, multi_tf.py, scorer.py --mode technical（侧重反转维度）
输出：trend_bear.md (~800-1200字)
  【1.多周期背离检测】(日线/60min 是否有 MACD 背离？)
  【2.RSI 极端区间】(超买/超卖+历史分位)
  【3.KDJ 极端信号】(J值>100或<0，低位金叉/高位死叉)
  【4.布林带极端位置】(突破上轨/触及下轨/带宽收窄预示变盘)
  【5.K线反转形态】(锤子线/吞没/十字星/三兵)
  【6.关键支撑/阻力】(前期高低点/密集成交区/斐波那契回撤)
  【7.反转派评分】(1-5星)
  【8.触发条件】🆕
    • 反转确认信号（什么形态+什么价位确认反转？）
    • 反转失败条件（突破哪个价位说明反转不成立？）
硬约束：
  - 不分析均线排列方向（那是 C1 的领域）
  - 不分析 ADX 趋势强度（那是 C1 的领域）
  - 必须同时标注信号的时间框架（日线/60min/周线）
预估耗时：60-180s
```

#### Phase 1c — 3 并行（技术裁判 + 宏观 + 同业对比）

**Agent C3：技术综合裁判** 🆕
```
角色：技术首席分析师——基于 C1/C2 的辩论，做最终裁决
原则：不看原始 K 线（C1/C2 已看过），只看双方的论据质量
      核心问题：当前市场更支持趋势延续还是均值回归？
输入：C1 报告全文 + C2 报告全文 + data_package.stock (仅用于事实核查)
脚本：无 (纯裁决推理)
输出：tech_judge.md (~1000-1500字)
  【1.论据对比】C1 vs C2 在各维度的论据对照表
  【2.时间框架冲突】(如周线趋势看多但日线反转看空——谁主导？)
  【3.最终择时分】-10~+10（基于 scorer.py technical 模式+裁判权衡）
  【4.关键价位裁决】支撑位/阻力位采用 C1 还是 C2 的判断？
    • 裁决后的关键价位（带触发条件说明）
  【5.多空力量对比】当前市场更支持趋势延续还是反转回归？
  【6.最终评级】🟢顺势做多 / 🟡观望等待 / 🔴择机做空 + 1-5星
  【7.确信度证据】🆕 (供后续自循环复盘)
    • 当前时间框架冲突程度（周/日/60min 方向一致=高确信/分歧=低确信）
    • 趋势派与反转派论据对比（C1论据数 : C2论据数）
    • 裁决依赖的关键形态/价位（如该形态失败，评级是否翻转？）
预估耗时：90-240s
```

**Agent P：同业分析师** 🆕
```
角色：行业研究员，精通可比公司分析和竞争格局判断
继承：comps-analysis-ashare 分析思路（数据源以中间层为准）
输入：data_package.stock (估值对比/规模对比)
      data_package.financial (ROE/毛利率/净利率/营收增速)
      B3 的行业信息 (用于确定可比公司范围)
脚本：无 (数据已结构化，做统计基准计算和位置解读)
输出：peer_report.md (~1200-1800字)

  【1.可比公司筛选】
    • 从概念成分股中筛选 5-10 家真正的可比公司
    • 排除：ST/新股(上市<1年)/营收或市值差距>10倍
    • 筛选依据：主营相似度、市值/营收规模接近度

  【2.运营效率对比】
    • ROE/毛利率/净利率/营收增速 四维统计基准表
      | 指标 | 目标 | 最小 | 25分位 | 中值 | 75分位 | 最大 |
    • 结论：目标在哪些维度领先、哪些维度落后

  【3.估值分位定位】
    • PE/PB/PS 三乘数统计基准表（同上格式）
    • 结论：目标处于什么分位带？溢价？折价？合理？

  【4.PE×ROE 交叉分析】
    • 四象限：性价比(Quality at Fair Price) / 质量溢价 / 价值陷阱 / 泡沫
    • 目标落在哪个象限？

  【5.竞争格局】
    • 同业的差异化特征（龙头 vs 追赶者 / 成长型 vs 价值型）
    • 目标在同业中的独特优势/劣势

  【6.同业结论】
    • 一句话：目标在同业中处于什么位置，估值是否合理

预估耗时：90-240s
```

**Agent G：宏观经济学家** 🆕
```
角色：宏观策略研究员（10年经验）
继承：无 (六家都缺)
输入：data_package.macro (CPI/PMI/LPR/社融/信用利差/汇率)
      data_package.market (指数/北向 作为辅助)
      B3 的行业裁决信息 (用于宏观→行业映射)
脚本：无 (纯推理)
输出：macro_report.md (~1000-1500字)
  【1.经济周期定位】【2.货币信用环境】【3.外部环境】
  【4.对目标股的宏观影响(顺风/中性/逆风)】【5.宏观风险事件】
预估耗时：90-240s
```

#### Phase 2 — 2 并行（交叉分析层，依赖全部 P1 报告）

**Agent D：资金博弈师**
```
角色：资金流分析师，精通龙虎榜和筹码博弈
继承：chris3cano 第三步(博弈) + ST框架
增强：机构持仓变化追踪（通过分析师数据+研报+基金持仓）
输入：data_package.stock (个股资金流/龙虎榜/股东户数/融资融券/大宗交易/增减持/研报/基金持仓)
      P1 全部报告 (A/B3/C3/G) — 含多空辩论结果
脚本：无 (纯推理，数据已结构化)
输出：flow_report.md (~1200-1800字)
  【1.主力资金】【2.龙虎榜】【3.筹码分布】【4.融资融券】
  【5.大宗交易】【6.机构行为（研报趋势+基金持仓变化+增减持）】
  【7.情绪综合】【8.ST博弈】(如适用)
硬约束：
  - 不把板块资金流/北向资金说成个股信号
  - 龙虎榜数据为近月统计，注意时效
预估耗时：60-180s
```

**Agent E：交易策略师**
```
角色：交易策略师，专注买卖决策和风险管理
继承：biga 三信号交叉 + 目标/止损
增强：历史信号胜率验证(validator.py)
输入：P1 全部报告 (A/B3/C3/G) — B3 基本面裁决 + C3 技术裁决作为核心输入
脚本：scorer.py --mode full, signal.py, validator.py
输出：trade_signal.md (~1500-2000字)
  【1.综合评分(0-100)】【2.信号交叉决策】
  【3.历史验证(胜率/平均收益/最大回撤)】
  【4.多空共振】【5.操作建议】🆕 每条建议带触发条件
    • 方向 + 仓位（首次/加仓/减仓 分档 + 触发价）
    • 止损（价格 + 触发条件："跌破 ¥170 且当日收盘未收回"）
    • 目标（三档价格 + 到达后操作："到达 ¥195 视量能决定是否上调"）
  【6.分档操作计划】🆕 含触发条件变更
硬约束：
  - 信号决策基于signal.py输出，不自行编造
  - 仓位≤20%(单只风控)
  - 催化剂+热度是唯二LLM主观判断维度(共25分)
  - 必须声明"不构成投资建议"
预估耗时：90-240s
```

#### Phase 2b — 1 串行（合规质检层）

**Agent I：合规质控师** 🆕
```
角色：合规与质量控制官，专职流程审计 + 数据校对
继承：无 (六家都缺)
定位：形式层——在纠偏之前，先确保材料本身没有错误。
      两个职责：
        职责一：流程合规 — 各子 Agent 是否严格遵守了规范？
        职责二：数据质控 — 报告中的数字是否与原始数据一致？
      这是「形式审查」：小错误、编造、违规取数先纠正，
      材料干净了才交给纠偏师做「实质性质疑」。

输入：全部 11 份报告 (B1/B2/C1/C2/A/G + B3/C3 + D/E) + data_package
脚本：无 (纯比对推理)
输出：compliance_report.md (~1000-1500字)

  ── 职责一：流程合规 ──
  【1.取数纪律】逐 Agent 检查：
    • 是否有 Agent 自行调用了中间层/akshare/web_search？
    • 是否有 Agent 自行计算了本应由脚本计算的指标？
    • 各 Agent 的输出格式是否与 brief 规定的模板一致？
    • 数据引用是否标注了来源函数？

  ── 职责二：数据质控 ──
  【2.数字校验】逐报告对照 data_package：
    • 报告中引用的关键数字（价格/PE/涨跌幅/财务指标等）是否与 data_package 一致？
    • 是否存在明显的数据单位错误？
    • 是否存在编造痕迹？
    • 多个报告中引用的同一数据点是否一致？

  ── 综合 ──
  【3.合规结论】✅ 全通过 / ⚠️ N项轻微问题 / 🚫 N项严重违规
  【4.问题清单】逐条列出，标注严重程度和涉及的 Agent
  【5.是否建议首席驳回】严重违规时建议 Agent F 退回问题报告要求重做

预估耗时：90-180s
```

#### Phase 2c — 1 串行（纠偏层，依赖 P2b 合规通过的全部报告）

**Agent H：纠偏与风控师** 🆕
```
角色：风控总监 + 纠偏者，专职质疑和 bias 检测
继承：无 (六家都缺)
定位：实质层——合规(I)确认材料无形式错误后，H 做实质性质疑。
      不是计算器，是挑战者——读取已通过合规检查的全部报告，挑出：
        • 哪个 Agent 的结论与自己的数据矛盾？
        • 哪个判断过度乐观或过度悲观？
        • 哪个逻辑链条有跳跃？
        • 多个 Agent 之间是否存在结论互斥？

输入：全部 11 份报告 + compliance_report(I) + data_package
      + risk_quant.py 的运行结果（主 Agent 在 Step 2c 前执行）
脚本：无 (纯推理——不自行计算任何指标)
输出：bias_report.md (~1500-2000字)
  【1.乐观偏差检测】报告中过度看多的论断，对照数据核查
  【2.悲观偏差检测】报告中过度看空的论断，对照数据核查
  【3.逻辑一致性】各报告结论 vs 报告内数据的自洽性
  【4.跨模块矛盾】A说牛B说熊，谁对？能不能裁决？
  【5.假设质疑】各报告依赖的关键假设是否成立
  【6.风控红线】基于 risk_quant 结果，指出哪些建议超出了可接受风险范围
  【7.一句话纠偏结论】

预估耗时：120-240s
```

**risk_quant.py 的执行**：由主 Agent 在 Step 2c 派发 Agent H 之前执行，结果注入 H 的 context。

#### Phase 3a — 2 并行（首席辩论：市场错误 vs 市场有效）

**Agent F1：市场错误论者** 🆕
```
角色：投资论文作者——全力论证"我们发现了市场的错误定价"
原则：继承阿克曼三问中的 Q1+Q3。差异化认知责任在此 Agent。
      核心问题：凭什么我们比市场聪明？
输入：全部 11 份报告 + compliance_report(I) + bias_report(H)
      + B3 的错误定价诊断 + E 的催化剂矩阵
脚本：无 (纯推理)
输出：thesis_bull.md (~1200-1800字)

  【Q1.错误定价论证】
    • 市场共识是什么？（一句话）
    • 共识模型的关键假设漏洞在哪？（引用 B3 的诊断）
    • 错误定价类型：___（来自 B3 的六分类诊断）
    • 数据支撑：B1 的多头论据 + C1 的趋势信号 + E 的催化剂

  【Q2.催化剂路径】
    • 核心催化剂（引用 E 的催化剂矩阵）
    • 预期时间窗口 + 各阶段里程碑
    • 如催化剂未兑现：F1 的论点是否依然成立？

  【Q3.差异化认知】🆕 (F1 专属)
    • 我们看到了什么市场没看到的？
    • 认知优势来源：数据深度？分析框架？行业经验？时间维度？
    • 一页纸检验：用一段话写出「我看到别人没看到的」
    • 如果写不出 → 标注「未发现差异化认知，基于公开信息做判断」

  【确信度】1-10 分 (基于论据质量)

预估耗时：120-300s
```

**Agent F2：市场有效论者** 🆕
```
角色：魔鬼辩护人——全力论证"市场永远是对的"
原则：否定 F1 的差异化认知。不是找反方数据（B2/C2 已做过），
      而是质疑 F1 的推理链本身。
      核心问题：如果市场是对的，我们漏掉了什么？
输入：全部 11 份报告 + F1 的 thesis_bull.md
      + B2 的空头论据 + C2 的反转信号
脚本：无 (纯推理)
输出：thesis_bear.md (~1000-1500字)

  【挑战 F1 的产业链】(逐一攻击)
    • Q1挑战：F1 的"市场共识"是否真的存在？证据在哪？
    • Q2挑战：催化剂的确定性/时间性/可控性/不可逆性中哪个最弱？
    • Q3挑战：F1 的"差异化认知"是真正的认知优势还是幻觉？
       - 如果是信息深度优势 → 这个信息别人也能拿到吗？
       - 如果是分析框架优势 → 框架本身有漏洞吗？
       - 如果是行业经验优势 → 经验在当下环境还适用吗？
       - 如果是时间维度优势 → 市场为什么等不了那么久？

  【市场正确的可能解释】
    • 市场看到但我们分析中遗漏的风险（流动性/政策/治理/行业逆风）
    • B2 空头论据中哪些可能是市场定价的真正原因？

  【确信度】1-10 分 (基于对 F1 论据的摧毁程度)

预估耗时：120-300s
```

#### Phase 3b — 1 串行（首席裁决）

**Agent F：首席综合官**
```
角色：首席分析师（15年经验），终极裁决
继承：chris3cano 第四步(决策) + cn-stock 报告模板 + 阿克曼三问
增强：裁定 F1 vs F2 的辩论 + 最终投资论文 + 退出标准
输入：全部 11 份报告 + compliance_report(I) + bias_report(H)
      + F1 thesis_bull.md + F2 thesis_bear.md
      + data_package (事实核查)
脚本：无 (纯推理)
输出：final_report.md (~3000-5000字)
  一、市场全景 (来自 A + G)
  二、标的选择
    2.1 基本面辩论 (B1 vs B2 → B3 裁决)
    2.2 技术面辩论 (C1 vs C2 → C3 裁决)
  三、资金博弈 (来自 D)
  四、交易决策 (来自 E)
  五、风险量化 (来自 H)
  六、首席裁决
    6.1 F1 vs F2 辩论裁决 🆕
      • 核心分歧：F1 说「市场错了，因为___」vs F2 说「市场对，我们漏了___」
      • 裁决：哪方论据更硬？差异化认知是否成立？
      • 如果裁决 F1 胜 → 基于认知优势下注
      • 如果裁决 F2 胜 → 标注「未发现优于市场的判断，不建议主动交易」
    6.2 投资论文 —— 阿克曼三问
      Q1: 为什么被错误定价？(引用 B3 诊断 + F1/F2 裁决)
      Q2: 什么会改变市场认知？(引用 E 催化剂矩阵)
      Q3: 我们的差异化认知是什么？(引用 F1 输出 + F2 挑战结果)
    6.3 退出标准（三类）
      1. 论文实现 · 2. 论文失效 · 3. 机会成本
    6.4 盲区标注 (数据不足以判断的部分)
    6.5 确信度矩阵
      | 维度 | 确信度 | 共识强度 | 辩论结果 |
      | 基本面 | ★★★★☆ | B1/B2分歧=低 | |
      | 技术面 | ★★★☆☆ | C1/C2分歧=中 | |
      | 综合(F1 vs F2) | ★★★☆☆ | F1胜/F2胜/平局 | F裁决 |
    6.6 一句话结论 (≤50字)
  七、附录
    7.1 数据来源与方法
    7.2 评分明细表
    7.3 免责声明
硬约束：
  - 团队分歧如实呈现，不“和谐”
  - 矛盾不可裁决时标注“团队分歧，建议人工判断”
  - 关键数据必须标注来源函数
  - 投资论文三步必须回答完整
预估耗时：180-480s (最重的推理任务)
```

---

## 三、数据层：中间层对接与补齐

### 3.1 Step 0 数据采集清单

主 Agent 在 Step 0 执行 `execute_code` 批量调用以下函数，组装为 `data_package`。

#### 市场级数据（→ Agent A, G）

| # | 函数 | 用途 | 源 | 并发组 |
|---|------|------|-----|:--:|
| 1 | `get_index_quotes()` | 10大指数实时快照 | ft+tx | Batch1 |
| 2 | `get_market_breadth()` | 新高/新低比 | 直调 | Batch1 |
| 3 | `get_market_activity()` | 涨跌停家数 | akshare HTML | Batch2 |
| 4 | `get_northbound_flow()` | 北向资金(市场级) | legulegu | Batch2 |
| 5 | `get_margin_summary()` | 两融余额(市场级) | composite | Batch3 |
| 6 | `get_board_spot("industry")` | 131行业涨跌排名 | PAE | Batch3 |
| 7 | `get_concept_spot()` | 概念板块排名 | PAE | Batch3 |
| 8 | `get_board_fund_flow("industry")` | 行业资金流 | PAE | Batch4 |
| 9 | `get_board_fund_flow("concept")` | 概念资金流 | PAE | Batch4 |
| 10 | `get_macro_indicators()` 🆕 | CPI/PMI/LPR/社融/利差/汇率 | 待建 | Batch4 |
| 11 | 循环 `get_board_spot("industry")` × 20日 | 板块轮动历史 | PAE | Batch5 |

#### 个股级数据（→ Agent B, C, D, E, H）

| # | 函数 | 用途 | 源 | 并发组 |
|---|------|------|-----|:--:|
| 12 | `get_realtime_quote(symbol)` | 实时行情 | tx | Batch1 |
| 13 | `get_daily_kline(symbol)` | 日K线(默认365日) | tx_http | Batch1 |
| 14 | `get_weekly_kline(symbol)` 🆕 | 周K线 | 待建 | Batch2 |
| 15 | `get_minute_kline(symbol, "60")` | 60分钟K线 | sina_http | Batch2 |
| 16 | `get_minute_kline(symbol, "30")` | 30分钟K线 | sina_http | Batch2 |
| 17 | `get_individual_fund_flow(symbol)` | 个股主力资金 | PAE | Batch3 |
| 18 | `get_valuation_comparison(symbol)` | PE/PB/PEG + 行业中值 | EM | Batch3 |
| 19 | `get_scale_comparison(symbol)` | 市值/营收/净利 + 行业排名 | EM | Batch3 |
| 20 | `get_company_profile(symbol)` | 主营/产品/经营范围 | EM | Batch4 |
| 21 | `get_profit_forecast_eps(symbol)` | 盈利预测 EPS | EM | Batch4 |
| 22 | `get_profit_forecast_metrics(symbol)` | 盈利预测综合指标 | EM | Batch4 |
| 23 | `get_lhb_stat(symbol)` | 龙虎榜统计 | ext | Batch5 |
| 24 | `get_shareholder_count(symbol)` | 股东户数变化 | EM | Batch5 |
| 25 | `get_top10_shareholders(symbol)` | 十大股东 | EM | Batch5 |
| 26 | `get_margin_detail(symbol, date)` | 个股融资融券 | composite | Batch6 |
| 27 | `get_dzjy_stat(symbol)` | 大宗交易统计 | ext | Batch6 |
| 28 | `get_shareholder_changes(symbol)` | 重要股东增减持（已有，非待建） | ths | Batch6 |
| 29 | `get_convertible_bond_info(symbol)` 🆕 | 可转债信息 | 不做 | — |
| 30 | `get_index_kline("000300")` | 沪深300 K线(Beta计算用) | ft/sina | Batch7 |

#### 财务级数据（→ Agent B）

| # | 函数 | 用途 | 源 | 并发组 |
|---|------|------|-----|:--:|
| 31 | `get_financial_abstract(symbol)` | 财务摘要(ROE/毛利率/净利率/营收/净利润) | 第二中间层 | Batch7 |
| 32 | `get_financial_indicators(symbol)` | 财务指标(负债率/流动比率/现金流等) | 第二中间层 | Batch7 |
| 33 | `get_dupont(symbol)` | 杜邦分解 | 第二中间层 | Batch8 |
| 34 | `get_growth_comparison(symbol)` | 成长性对比 | 第二中间层 | Batch8 |

**并发规则**：同源 ≤2 并发，BaoStock 源禁止并发。总采集约 8 批，每批间隔 1-2s。总耗时 ~10-15s。

### 3.2 中间层补齐优先级

| 优先级 | 函数 | 阻塞的 Agent | 说明 |
|:--:|------|:--:|------|
| 🔴 P0 | 财务中间层 8 函数搬迁 | B | Agent B 的 80% 数据来源，无此则基本面分析为空心 |
| 🟡 P1 | `get_weekly_kline(symbol)` | C | 不需要——3年日线聚合即可，已测试可行 |
| 🟡 P1 | `get_macro_indicators()` | G | Agent G 的唯一数据来源，第三中间层待建 |
| 🟡 P1 | ~~`get_insider_trades(symbol)`~~ | D | ✅ 已有 `get_shareholder_changes`，字段完整 |
| 🟢 P2 | `get_convertible_bond_info(symbol)` | D | 可转债信号 |
| 🟢 P2 | `get_board_spot_history(days=20)` | A | 轮动追踪。可用循环调用替代，非阻塞 |
| 🟢 P2 | `get_industry_financial_aggregates(board)` | B | 行业财务中位数 |
| 🔵 P3 | `get_analyst_rating_changes(symbol)` | B | 锦上添花 |
| 🔵 P3 | `get_news_sentiment(symbol)` | D | 锦上添花 |

---

## 四、计算层：10 脚本清单

所有脚本放在 `a-share-analyst/scripts/` 下。输入来自 `data_package` 的 JSON 字段，输出为结构化 JSON（供 Agent 解读）或文本（供报告引用）。

### 4.1 继承脚本（5个）

#### `ta.py` — 技术指标计算
```
继承自：geek-a-share-analyst/scripts/technical_analysis.py
融合：cn-stock-analyst 指标规则表
输入：日K线 OHLCV (DataFrame) + 实时行情
输出：{
  "ma": {"MA5": [...], "MA10": [...], ..., "arrangement": "多头排列"},
  "macd": {"DIF": [...], "DEA": [...], "hist": [...], "signal": "金叉买入", "divergence": "顶背离"},
  "rsi": {"value": 62.3, "zone": "正常"},
  "kdj": {"K": [...], "D": [...], "J": [...], "signal": "金叉"},
  "boll": {"upper": [...], "mid": [...], "lower": [...], "position": "中轨上方", "bandwidth": "收窄"},
  "atr": {"value": 2.35, "pct": 1.2},
  "volume": {"ratio": 1.8, "trend": "放量上涨"},
  "candlestick": [{"date": "2026-06-12", "pattern": "锤子线", "direction": "bullish"}, ...]
}
函数签名：compute_all(df: pd.DataFrame, quote: dict = None) -> dict
```

#### `scorer.py` — 多维度评分引擎
```
继承自：biga 四维评分 + 创新基本面评分
模式：
  --mode technical   → 择时分(-10~+10) + 趋势突破分(0~15) + 入场就绪度(0~10)
  --mode fundamental → 基本面分(0~25)
  --mode full        → 全维度综合分 + 风控标记
输入：JSON (K线数据 + 行情数据 + ta.py输出 + 估值数据 + 财务数据)
输出：{
  "technical_timing": -10~+10,
  "valuation": 0~15,
  "trend_breakout": 0~15,
  "entry_readiness": 0~10,
  "fundamental_quality": 0~25,
  "risk_flags": [...],
  "auto_score": 0~75
}
函数签名：compute_scores(mode: str, data: dict) -> dict
```

#### `signal.py` — 三信号交叉决策矩阵
```
继承自：biga 三信号交叉
输入：scorer.py 的 full 模式输出 JSON
输出：{
  "decision": "最佳买点" | "接近买点" | "启动信号" | "追高风险" | "等待" | "超跌关注",
  "confidence": 0~100,
  "reason": "...",
  "suggested_position_pct": 20,
  "stop_loss": 170.50,
  "target_optimistic": 210.00,
  "target_base": 195.00,
  "target_conservative": 180.00
}
函数签名：cross_decision(scores: dict) -> dict
```

#### `theme_detector.py` — 主线识别辅助
```
继承自：Wind 6步主线的第1-4步数据化
输入：data_package.market (指数/宽度/行业/概念排名)
输出：{
  "environment": {"stage": "震荡偏强", "evidence": [...]},
  "main_themes": [{"name": "AI", "strength": 8.5, "duration_days": 5}, ...],
  "pseudo_themes": [...],
  "leaders": {"emotional": [...], "institutional": [...], "catchup": [...]},
  "sentiment_cycle": {"stage": "主升", "evidence": [...]}
}
函数签名：analyze_market_structure(market_data: dict) -> dict
```

#### `screener.py` — 多因子选股
```
继承自：niuniu-quant select 模块架构
输入：data_package (全市场扫描数据)
输出：DataFrame (筛选结果)
函数签名：screen(filters: dict) -> pd.DataFrame
状态：Phase 3 实现，非首批
```

### 4.2 创新脚本（5个）🆕

#### `validator.py` — 历史信号胜率验证
```
用途：盲区1 — 历史信号验证
输入：日K线 + 信号类型 + 回溯窗口
输出：{
  "signal": "MACD金叉",
  "historical_occurrences": 23,
  "win_rate_5d": 0.61,
  "win_rate_10d": 0.52,
  "win_rate_20d": 0.43,
  "avg_return_20d": 2.3,
  "max_drawdown_20d": -8.5,
  "confidence": "中等",
  "signal_decay": "该信号在10日后衰减明显"
}
函数签名：validate_signal(kline_df: DataFrame, signal_type: str, lookback: int = 500) -> dict
```

#### `multi_tf.py` — 多时间框架分析
```
用途：盲区2 — 五周期共振/背离
输入：日线/周线/60min/30min/15min K线
输出：{
  "weekly": {"trend": "上升", "macd": "金叉第3周"},
  "daily": {"trend": "震荡", "macd": "死叉第5日"},
  "60min": {"trend": "下降", "macd": "底背离"},
  "30min": {"trend": "盘整", "boll": "收窄"},
  "alignment": "部分背离",
  "alignment_detail": "周线看多但日线震荡，60分钟底背离可能先反弹",
  "dominant_tf": "周线"
}
函数签名：analyze_multi_timeframe(kline_dict: dict) -> dict
```

#### `risk_quant.py` — 量化风控
```
用途：盲区3 — VaR/回撤锥/压力测试
输入：日K线 + 基准指数K线
输出：{
  "var_95_1d": -3.8,
  "var_99_1d": -7.2,
  "cvar_95_1d": -5.1,
  "max_drawdown": -28.5,
  "max_drawdown_duration_days": 94,
  "volatility_annual": 0.35,
  "beta": 1.12,
  "beta_stability": "稳定",
  "drawdown_distribution": {"p50": -3.2, "p75": -8.5, "p90": -15.3, "p95": -21.0},
  "stress_test": {
    "market_down_10pct": -12.3,
    "market_down_20pct": -24.1,
    "liquidity_crisis": -18.5
  },
  "risk_budget": {
    "suggested_position_95var": 0.26,
    "suggested_position_99var": 0.14
  }
}
函数签名：compute_risk_metrics(kline_df: DataFrame, benchmark_df: DataFrame = None) -> dict
```

#### `earnings_surprise.py` — 业绩预期差
```
用途：盲区5 — 预测 vs 实际对比
输入：盈利预测数据 + 实际财报数据
输出：{
  "latest_quarter": "2026Q1",
  "forecast_eps": 5.20,
  "actual_eps": 5.45,
  "surprise_pct": 4.8,
  "surprise_direction": "beat",
  "historical_beat_rate": 0.75,
  "market_reaction_typical": "+1.2%",
  "guidance_change": "上调"
}
函数签名：compute_earnings_surprise(forecast: dict, actuals: dict) -> dict
```

#### `rotation.py` — 板块轮动追踪
```
用途：盲区6 — 板块排名的时序分析
输入：近20日板块排名数据 (DataFrame)
输出：{
  "current_leaders": ["半导体", "AI", "光模块"],
  "leader_duration": {"半导体": 5, "AI": 8, "光模块": 3},
  "rotation_speed": 0.42,
  "rotation_phase": "主线强化",
  "emerging_themes": ["液冷", "HBM"],
  "fading_themes": ["光伏", "锂电"],
  "sector_correlation": 0.78
}
函数签名：analyze_rotation(board_spot_history: DataFrame) -> dict
```

### 4.3 脚本依赖关系

```
ta.py (无依赖)
    ↓
multi_tf.py → ta.py (复用指标计算)
    ↓
scorer.py → ta.py (复用MACD/RSI/KDJ信号) + multi_tf.py (多周期信号)
    ↓
signal.py → scorer.py (复用评分)
    ↓
validator.py → ta.py (复用信号检测) + scorer.py (复用评分)

risk_quant.py (无依赖，纯统计)
earnings_surprise.py (无依赖，纯对比)
rotation.py (无依赖，纯时序分析)
theme_detector.py (无依赖，纯排名聚合)
screener.py (无依赖，纯筛选)
```

---

## 五、执行流程与时序

### 5.1 阶段图

```
Step 0: 主 Agent 数据采集
  │
  │ data_package 产出
  │
  ├─ Step 1: delegate_task(batch) ─ [B1 ∥ B2 ∥ A]
  │   超时: 900s × 3 (并行)
  │   产出: fundamental_bull.md, fundamental_bear.md, market_report.md
  │
  ├─ Step 1b: delegate_task(batch) ─ [B3 ∥ C1 ∥ C2]
  │   超时: 900s × 3 (并行)
  │   依赖: P1 (B1+B2→B3; C1/C2 独立)
  │   产出: fundamental_judge.md, trend_bull.md, trend_bear.md
  │
  ├─ Step 1c: delegate_task(batch) ─ [C3 ∥ G ∥ P]
  │   超时: 900s × 3 (并行)
  │   依赖: P1b (C1+C2→C3; B3→G/P)
  │   产出: tech_judge.md, macro_report.md, peer_report.md
  │
  ├─ Step 2: delegate_task(batch) ─ [D ∥ E]
  │   超时: 900s × 2 (并行)
  │   依赖: P1+P1b+P1c 全部 (A/B3/C3/G)
  │   产出: flow_report.md, trade_signal.md
  │
  ├─ Step 2b: delegate_task ─ [I]
  │   超时: 900s
  │   依赖: 全部 11 份报告
  │   产出: compliance_report.md
  │
  ├─ Step 2c: delegate_task ─ [H]
  │   超时: 900s
  │   依赖: 全部 11 份报告 + compliance_report
  │   产出: bias_report.md
  │
  ├─ Step 3a: delegate_task(batch) ─ [F1 ∥ F2]
  │   超时: 900s × 2 (并行)
  │   依赖: 全部 11 份报告 + compliance + bias
  │   产出: thesis_bull.md, thesis_bear.md
  │
  └─ Step 3b: delegate_task ─ [Agent F]
      超时: 900s
      依赖: 全部 11 份报告 + compliance + bias + F1 + F2
      产出: final_report.md
```

### 5.2 依赖矩阵

```
            A  B1 B2 B3 C1 C2 C3  G  D  E  I  H  F1 F2 F
Agent A     -   -  -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓  ✓  ✓
Agent B1    -   -  -  ✓  -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓
Agent B2    -   -  -  ✓  -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓
Agent B3    -   -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✓
Agent C1    -   -  -  -  -  -  ✓  -  -  -  ✓  ✓  ✓  ✓  ✓
Agent C2    -   -  -  -  -  -  ✓  -  -  -  ✓  ✓  ✓  ✓  ✓
Agent C3    -   -  -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓  ✓  ✓
Agent G     -   -  -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓  ✓  ✓
Agent D     -   -  -  -  -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓
Agent E     -   -  -  -  -  -  -  -  -  -  ✓  ✓  ✓  ✓  ✓
Agent I     -   -  -  -  -  -  -  -  -  -  -  ✓  ✓  ✓  ✓
Agent H     -   -  -  -  -  -  -  -  -  -  -  -  ✓  ✓  ✓
Agent F1    -   -  -  -  -  -  -  -  -  -  -  -  -   -  ✓
Agent F2    -   -  -  -  -  -  -  -  -  -  -  -  -   -  ✓
Agent F     -   -  -  -  -  -  -  -  -  -  -  -  -   -  -
```

读法：行依赖列。B3 依赖 B1+B2；C3 依赖 C1+C2；D/E 依赖 A/B3/C3/G。

### 5.3 阶段并行度

每个子 Agent 的 context 包含：

```
══════════════════════════════════════════════════
[角色简报]
{references/agent-X-brief.md 全文}

[数据]
{从 data_package 提取的领域数据子集，JSON格式}

[前置报告]（仅 P2/P3 Agent）
{依赖的 Agent 产出的报告全文}

[任务指令]
1. 分析步骤（按简报中的框架执行）
2. 如需计算：terminal 执行 scripts/<name>.py --input '<json>'
3. 输出格式：（按简报中的模板）
4. 硬约束：（按简报中的约束列表）

[注意]
- max_iterations 未硬限制，但超时 900s 自动终止
- 不要在 report 中包含原始 JSON 数据，只引用关键数字
- 如果数据不足以判断，标注"数据不足"而非编造
══════════════════════════════════════════════════
```

---

## 六、文件清单

```
a-share-analyst/          # ~/.hermes/skills/a-share-analyst/
├── SKILL.md                              # Hermes skill 入口 + 调度规则
│
├── scripts/
│   ├── __init__.py
│   ├── ta.py                             # 技术指标计算（继承 geek + cn-stock）
│   ├── scorer.py                         # 多维度评分引擎（继承 biga + 创新）
│   ├── signal.py                         # 三信号交叉决策矩阵（继承 biga）
│   ├── theme_detector.py                 # 主线识别辅助（继承 Wind）
│   ├── screener.py                       # 多因子选股（继承 niuniu）[Phase 3]
│   ├── validator.py                      # 历史信号胜率验证 🆕
│   ├── multi_tf.py                       # 多时间框架分析 🆕
│   ├── risk_quant.py                     # 量化风控 🆕
│   ├── earnings_surprise.py              # 业绩预期差 🆕
│   └── rotation.py                       # 板块轮动追踪 🆕
│
├── references/
│   ├── agent-a-brief.md                  # Agent A 市场策略师简报
│   ├── agent-b1-brief.md                 # Agent B1 多头分析师简报 🆕
│   ├── agent-b2-brief.md                 # Agent B2 空头分析师简报 🆕
│   ├── agent-b3-brief.md                 # Agent B3 基本面裁判简报 🆕
│   ├── agent-c1-brief.md                 # Agent C1 趋势派技术分析师简报 🆕
│   ├── agent-c2-brief.md                 # Agent C2 反转派技术分析师简报 🆕
│   ├── agent-c3-brief.md                 # Agent C3 技术裁判简报 🆕
│   ├── agent-g-brief.md                  # Agent G 宏观经济学家简报 🆕
│   ├── agent-p-brief.md                  # Agent P 同业分析师简报 🆕
│   ├── agent-d-brief.md                  # Agent D 资金博弈师简报
│   ├── agent-e-brief.md                  # Agent E 交易策略师简报
│   ├── agent-h-brief.md                  # Agent H 纠偏与风控师简报 🆕
│   ├── agent-i-brief.md                  # Agent I 合规质控师简报 🆕
│   ├── agent-f-brief.md                  # Agent F 首席综合官简报
│   ├── ta-rules.md                       # 技术指标规则表（来自 cn-stock）
│   ├── scoring-matrix.md                 # 评分矩阵详解（来自 biga）
│   ├── sector-matrix.md                  # 板块分析框架（来自 biga）
│   ├── valuation-guide.md                # 估值分档表（来自 cn-stock）
│   ├── sentiment-cycle.md                # 情绪周期判断标准（来自 Wind）
│   ├── candlestick-patterns.md           # K线形态识别（来自 geek）
│   └── report-template.md                # 最终报告模板
│
└── tests/
    ├── __init__.py
    ├── test_ta.py
    ├── test_scorer.py
    ├── test_signal.py
    ├── test_validator.py
    ├── test_multi_tf.py
    ├── test_risk_quant.py
    ├── test_earnings_surprise.py
    ├── test_rotation.py
    └── test_theme_detector.py
```

**总计**：1 SKILL.md + 10 scripts + 16 references + 10 tests = 37 文件。

---

## 七、实施阶段

### Phase 0：中间层补齐（阻塞项）⏱ 2-3天

| 任务 | 说明 |
|------|------|
| 财务中间层 8 函数搬迁 | `get_financial_abstract` 等，Agent B 数据基础 |
| `get_weekly_kline(symbol)` | 日线聚合周线 OHLCV |
| `get_macro_indicators()` | 爬取/对接 CPI/PMI/LPR 等宏观数据 |
| `get_insider_trades(symbol)` | 高管增减持 |
| **验收**：4 函数可调用，返回结构化数据 |

### Phase 1：核心计算脚本 ⏱ 3-4天

| 任务 | 说明 |
|------|------|
| `ta.py` | 最高优先级。复用 geek 代码 + cn-stock 规则 |
| `scorer.py` | 依赖 ta.py。三种模式 |
| `signal.py` | 依赖 scorer.py |
| `multi_tf.py` | 依赖 ta.py |
| `validator.py` | 依赖 ta.py + scorer.py |
| **验收**：5 脚本可终端执行，返回正确 JSON，各有 test |

### Phase 2：创新脚本 + Agent 简报 ⏱ 2-3天

| 任务 | 说明 |
|------|------|
| `risk_quant.py` | VaR/回撤/压力测试 |
| `earnings_surprise.py` | 预期差计算 |
| `rotation.py` | 轮动追踪 |
| `theme_detector.py` | 主线数据化 |
| 8 份 agent brief | A/B/C/G/D/E/H/F |
| **验收**：全 10 脚本就绪，8 brief 审查通过 |

### Phase 3：调度层 + 端到端联调 ⏱ 2-3天

| 任务 | 说明 |
|------|------|
| SKILL.md 调度规则 | Step 0-1-1b-2-3 完整流程 |
| Step 0 data_package 组装 | execute_code 脚本 |
| 端到端测试 | 选 1-2 只股票完整跑通全流程 |
| `screener.py` | 可选，选股场景用 |
| 参考文档 | ta-rules / scoring-matrix / valuation-guide / sentiment-cycle / candlestick / report-template |
| **验收**：一只股票从输入到最终报告全流程通畅，报告质量可用 |

---

## 八、风险与约束

### 8.1 已知风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 财务中间层未就绪 | Agent B 分析空心化 | Phase 0 必须先完成 |
| delegate_task 批次上限 3 | Phase 1 只能 3 Agent 并行 | 已按此设计。P1b 串行是唯一妥协 |
| 子 Agent 超时 (900s) | 某个 Agent 分析过深导致超时 | Agent brief 中约束输出长度，明确「精炼 ≥ 冗长」 |
| 报告质量不一致 | 不同 Agent 产出的报告深度差异大 | Agent brief 中强制输出模板和字数范围 |
| API 限流 | 模型调用排队增加总耗时 | 非阻塞。实际总耗时估算 10-20 分钟 |
| 微信消息长度限制 | 最终报告 3000-5000 字可能截断 | 分段发送或提供文件下载 |
| 中间层函数变更 | 函数签名变化导致 data_package 组装失败 | Step 0 脚本必须在 a-share-market skill 加载后执行 |

### 8.2 硬约束（不可违反）

1. 子 Agent **不能调用 `delegate_task`**（不可递归派发）
2. 子 Agent **不能调用 `web_search`/`web_fetch`** 获取行情数据
3. 子 Agent **不能调用任何中间层函数或 akshare**——数据唯一来源是 context 中的 data_package 子集
4. 子 Agent **所有指标数值必须来自脚本输出，不自行计算**
5. 主 Agent 在 Step 0 **必须加载 `a-share-market` skill**
6. 最终报告中的**关键数据必须标注来源函数**
7. 所有脚本**必须有对应 test_**（在 tests/ 下）
8. **数据不够 → 标注「数据不足：缺少XXX」，不编造、不绕过、不降级获取**

### 8.3 确信度与自循环复盘（当前建立框架，Phase 4+ 实现闭环）

每个评级 Agent（B3/C3/D/G）输出的确信度 + 共识强度不是装饰分，而是**自循环复盘的输入数据**。

**当前阶段**：建立结构化确信度字段，统一格式，每次分析产出可机器读取的信度数据。

**后续闭环**（Phase 4+）：
```
历史分析记录（含确信度）
        ↓
  复盘验证（实际走势 vs 各 Agent 判断）
        ↓
  偏差分析（哪个 Agent 系统性偏乐观/偏悲观？B1永远压过B2？C2永远被C1碾压？）
        ↓
  权重调整 / prompt 纠偏 / 辩论规则修正
        ↓
  下次分析 → 学习后版本
```

**确信度数据结构**（每次分析产出，存 JSON）：
```python
conviction_record = {
    "timestamp": "2026-06-15T15:30:00",
    "symbol": "600519",
    "ratings": {
        "fundamental": {"agent": "B3", "stars": 4, "direction": "bull", "split": "B1:6 vs B2:2"},
        "technical": {"agent": "C3", "stars": 3, "direction": "neutral", "split": "C1:4 vs C2:3"},
        "flow": {"agent": "D", "stars": 4, "direction": "bull"},
        "macro": {"agent": "G", "stars": 4, "direction": "bull"},
    },
    "composite": {"agent": "F", "stars": 4, "resonance": "3_bull_1_neutral"},
    "trade_signal": {"agent": "E", "decision": "买入", "target_price": 195.0, "stop_loss": 170.0},
}
```

### 8.3a 阿克曼投资论文框架吸收（2026-06-15）

阿克曼的三问（Why cheap / What unlocks / How much）恰好对应 Agent B3/E/F 的核心输出，但暴露了三个缺失维度。

#### 吸收一：错误定价诊断 → Agent B3 输出新增

```python
# B3 的「论据质量评估」后新增诊断段：
"""
【X.错误定价类型诊断】🆕
  市场给这只股票当前价格的核心理由是什么？
  这个理由属于哪种错误定价类型？
    □ 分类错误——被贴上"旧经济"标签，实际有增长属性
    □ 短期导向——市场只看下季业绩，忽略3年转型效果
    □ 复杂性折价——业务多元，分拆估值远超整体
    □ 信息不对称——管理层已公开的信号未被市场定价
    □ 情绪过度——一次负面事件被定价为永久损害
    □ 指数/风格溢出——被动资金机械流出，与基本面无关
"""
```

#### 吸收二：催化剂矩阵 → Agent E 输出升级

当前 Agent E 的催化剂评分只有 0-15 分。升级为结构化催化剂矩阵：

```
Agent E 输出新增：
  【X.催化剂矩阵】🆕
    识别到的催化剂（按类型分类）：
      内部：□管理层更换 □资产出售 □回购增持 □新战略 □成本优化 □研发收获
      外部：□监管变化 □行业整合 □对手退出 □原材料/汇率 □指数纳入
      事件：□财报季 □股东大会 □产品发布 □诉讼结果 □重组披露
    
    催化剂质量评估（1-10/维）：
      · 确定性：___分（有明确时间表=高，模糊推测=低）
      · 时间性：___分（可预估窗口=高，完全不可知=低）
      · 可控性：___分（内部驱动=高，依赖外部=低）
      · 不可逆性：___分（发生后不可逆=高，可能反转=低）
    
    催化剂超时处理：
      · 预期窗口：___个月
      · 若超时未兑现 → 🚫 自动触发 reassessment（在合规报告中标注）
      · 若催化剂消失 → 🚫 thesis-break，建议重新评估
```

#### 吸收三：差异化认知 + 退出标准 → Agent F 投资论文升级

当前 Agent F 的「投资论文」是自由格式。升级为阿克曼三问结构：

```
Agent F 输出「投资论文」改为：
  6.2 投资论文 —— 阿克曼三问
  
    Q1: 为什么被错误定价？
      · 市场共识是什么？（一句话）
      · 共识模型的关键假设漏洞在哪？（具体可验证）
      · 错误定价类型：___（引用 B3 的诊断）
    
    Q2: 什么会改变市场认知？
      · 核心催化剂：___（引用 E 的催化剂矩阵）
      · 预期时间窗口：___个月
      · 催化剂未兑现时的处理：___
      · 能否主动推动？（机构适用，散户不适用）
    
    Q3: 我们的差异化认知是什么？
      · 我们看到了什么市场没看到的？
      · 认知优势来源：数据深度？分析框架？行业经验？时间维度？
      · 一页纸检验：如果写不清楚「我看到别人没看到的」，就没有差异化认知
    
  6.3 退出标准（三类）🆕
    1. 论文实现：目标价触发 → 催化剂兑现 → 市场重新定价完成
    2. 论文失效：核心假设被证伪 / 催化剂消失 / thesis-break条件触发
    3. 机会成本：找到更好标的 / 论文逻辑对但时间窗口拉太长

  纪律：一页纸原则
    · 6个模块填不满一页 → 逻辑不清晰，继续研究
    · 6个模块超过三页 → 太多臆测，数据支撑不足
```

### 8.3b 同业分析思路吸收（来自 comps-analysis-ashare，2026-06-15）

核心不是数据源（后续以中间层为准），是四套分析思路。→ 新增 Agent P。

**思路一：统计基准带，而非均值对比**

不说"PE 高于行业平均"，而是"PE=35x，行业中值=25x，处于 75 分位带"。

**思路二：PE×ROE 交叉——性价比判断**

高ROE+低PE=性价比，高ROE+高PE=质量溢价，低ROE+低PE=价值陷阱，低ROE+高PE=泡沫。

**思路三：按问题选指标**

贵不贵→PE/PB vs 中值；效率→毛利率/净利率/ROE；增速→营收增速 vs 75分位；性价比→PE×ROE。

**思路四：可比的筛选比可比的罗列更重要**——排除ST/新股/规模差距过大，只选5-10家真正可比的。

→ 新增 **Agent P（同业分析师）**，放入 P1c（与 C3、G 三路并行）。详见 §2.2 Phase 1c。

### 8.4 未覆盖的已知边界

- 港股/美股不在本 skill 范围（中间层未覆盖）
- 实时盘中分析 vs 收盘后分析的时间差异（先做收盘后版本）
- 批量分析多只股票（先做单只完整流程，批量是 Phase 4+）
- 定时自动分析（先用 cron 调度，skill 本身无 cron 感知）

---

## 附录 A：Agent 超时汇总

| Agent | 超时 | 并行 | 预估实际耗时 |
|-------|:--:|:--:|------|
| A (市场策略师) | 900s | P1 并行 | 60-180s |
| B1 (多头分析师) 🆕 | 900s | P1 并行 | 60-180s |
| B2 (空头分析师) 🆕 | 900s | P1 并行 | 60-180s |
| B3 (基本面裁判) 🆕 | 900s | P1b 并行 | 90-240s |
| C1 (趋势派技术) 🆕 | 900s | P1b 并行 | 60-180s |
| C2 (反转派技术) 🆕 | 900s | P1b 并行 | 60-180s |
| C3 (技术裁判) 🆕 | 900s | P1c 并行 | 90-240s |
| P (同业分析师) 🆕 | 900s | P1c 并行 | 90-240s |
| G (宏观经济学家) | 900s | P1c 并行 | 90-240s |
| D (资金博弈师) | 900s | P2 并行 | 60-180s |
| E (交易策略师) | 900s | P2 并行 | 90-240s |
| I (合规质控师) | 900s | P2b 串行 | 90-180s |
| H (纠偏与风控师) | 900s | P2c 串行 | 120-240s |
| F1 (市场错误论者) 🆕 | 900s | P3a 并行 | 120-300s |
| F2 (市场有效论者) 🆕 | 900s | P3a 并行 | 120-300s |
| F (首席综合官) | 900s | P3b 串行 | 180-480s |

## 附录 B：数据采集 script 模板

```python
# Step 0: execute_code 执行的 data_collection.py 骨架
from hermes_tools import terminal, read_file, write_file
import json, time, random

SYMBOL = "{{SYMBOL}}"  # 由主 Agent 注入

def call(func_name, *args, **kwargs):
    """封装中间层函数调用"""
    # 导入 + 调用 + 异常处理
    pass

results = {}

# Batch 1: 新浪/腾讯源 (2并发)
results["index"] = call("get_index_quotes")
results["breadth"] = call("get_market_breadth")
time.sleep(random.uniform(1, 2))

# Batch 2: PAE/直调源 (2并发)
results["activity"] = call("get_market_activity")
results["northbound"] = call("get_northbound_flow")
time.sleep(random.uniform(1, 2))

# ... (共约 8 批)

# 组装 data_package
data_package = {
    "market": {
        "index": results["index"],
        "breadth": results["breadth"],
        # ...
    },
    "stock": {
        "quote": results["quote"],
        "kline": results["kline"],
        # ...
    },
    "financial": {
        "abstract": results["fin_abstract"],
        # ...
    },
    "macro": results.get("macro", {}),
}

print(json.dumps(data_package, ensure_ascii=False, default=str))
```
