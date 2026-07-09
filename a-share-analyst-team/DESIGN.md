# a-share-analyst Skill · 增强版设计

> 首席分析师视角 · 团队作战 · 六家之上
> 不只是「取各家所长」，而是找到各家共同盲区，填补空白

---

## 零、六家共同盲区（Gap Analysis）

在逐份审阅 6 个 skill 后，发现它们有**10 个系统性共同缺陷**。不是某一家没做到，是全部六家都没做到。

| # | 盲区 | 六家状态 | 后果 |
|---|------|---------|------|
| 1 | **无历史信号验证** | 全部只做前向判断，零回测 | 说「MACD金叉买入」但历史上金叉后胜率是多少？不知道 |
| 2 | **无多时间框架分析** | 只有日线，无周线/60m/30m/15m | 日线金叉但周线死叉时该信谁？没答案 |
| 3 | **无量化风控** | 有止损概念(ATR)，无 VaR/回撤分布 | 止损设在-8%，但历史上这只股票单日最大跌幅是-15%，止损无效 |
| 4 | **无宏观锚定** | 框架提「宏观」，但无 CPI/PMI/利率/社融接入 | 「宏观利好」是 LLM 猜的，不是数据驱动的 |
| 5 | **无业绩预期差** | 有盈利预测数据，但无「实际 vs 预期」对比 | 知道机构预测 EPS=5.2，但实际报了 4.8 还是 5.8？缺对比 |
| 6 | **无板块轮动时间序列** | Wind 有单点主线识别，无时间序列追踪 | 知道「今天主线是 AI」，不知道「AI 是第三天还是第三周」 |
| 7 | **无极端事件压力测试** | 只有正常场景分析 | 「如果大盘跌 20%，这股票会跌多少？」没答案 |
| 8 | **无机构行为深度追踪** | 只有基本持仓数据，无增减持/社保/养老金动向 | 知道「机构持仓 12%」，不知道「上季度是 15% 还是 9%」 |
| 9 | **无产业上下游分析** | 全是个股独立分析 | 宁德时代跌了是因为锂矿涨了？没人告诉你 |
| 10 | **无可转债/衍生品信号** | 只分析正股 | 可转债折价 10% 说明什么？没人看 |

---

## 一、增强架构全景

```
                        ┌──────────────────────┐
                        │   主 Agent (首席)      │
                        │   数据采集 + 调度      │
                        │   含 宏观数据采集      │
                        └──┬────┬────┬────┬────┘
                           │    │    │    │
          ┌────────────────┘    │    │    └────────────────┐
          ↓                     ↓    ↓                      ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Agent A      │  │ Agent B      │  │ Agent C      │  │ Agent G  🆕  │
│ 市场策略师    │  │ 基本面分析师  │  │ 技术分析师    │  │ 宏观经济学家  │
│ 板块+主线    │  │ 财务+估值    │  │ 指标+多周期  │  │ CPI/PMI/利率 │
│ +轮动追踪 🆕 │  │ +预期差 🆕   │  │ +形态匹配 🆕 │  │ +信用/社融   │
│ +压力测试 🆕 │  │ +上下游 🆕   │  │              │  │              │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       └────────┬────────┴────────┬────────┴────────┬────────┘
                ↓                 ↓                 ↓
       ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
       │ Agent D      │  │ Agent E      │  │ Agent H  🆕  │
       │ 资金博弈师    │  │ 交易策略师    │  │ 量化风控师    │
       │ +机构追踪 🆕 │  │ +历史验证 🆕 │  │ VaR/回撤/锥  │
       │ +可转债 🆕   │  │ +多空共振 🆕 │  │ 压力测试执行  │
       └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
              │                 │                 │
              └────────┬────────┴────────┬────────┘
                       ↓                 ↓
              ┌──────────────────────────────────┐
              │ Agent F: 首席综合官               │
              │ 交叉质证 + 矛盾裁决 + 投资论文    │
              │ + 盲区标注 🆕                     │
              └──────────────────────────────────┘
```

**8 个 Agent，4 阶段**（`delegate_task` 每批最多 3 并行）：

| 阶段 | Agent | 角色 | 继承 | 增强 🆕 |
|:--:|------|------|------|------|
| **P1** | A | 市场策略师 | Wind 主线 + biga 择时 | 板块轮动时间序列、压力测试 |
| **P1** | B | 基本面分析师 | chris3cano 选股 + cn-stock 估值 | 业绩预期差、产业链上下游 |
| **P1** | C | 技术分析师 | geek ta.py + cn-stock 规则 | 多时间框架(日/周/60m/30m/15m) |
| **P1b** | G | 宏观经济学家 🆕 | — | CPI/PMI/利率/社融/信用利差 |
| **P2** | D | 资金博弈师 | chris3cano 博弈 + ST 框架 | 机构持仓变化追踪、可转债信号 |
| **P2** | E | 交易策略师 | biga 交叉信号 + 目标 | 历史信号胜率验证 |
| **P2** | H | 量化风控师 🆕 | — | VaR/CVaR/回撤锥/压力测试执行 |
| **P3** | F | 首席综合官 | chris3cano 四件套 + cn-stock 模板 | 盲区标注、矛盾裁决、置信度评级 |

**并发分布**：

```
Phase 1:  [A ∥ B ∥ C]  →  3 report
Phase 1b: [G]          →  1 report  (串行但可紧接P1)
Phase 2:  [D ∥ E ∥ H]  →  3 report  (依赖 P1 全部 4 份)
Phase 3:  [F]          →  最终报告   (依赖全部 7 份)
```

---

## 二、补齐的 10 个盲区：具体方案

### 盲区 1：历史信号验证 → `scripts/validator.py`

**问题**：6 家 skill 全部是「现在出现了金叉，所以买入」。但从不说「历史上这只股票出现金叉后，20 日胜率是多少」。

**方案**：`validator.py` — 信号历史回测引擎

```python
def validate_signal(symbol: str, kline_df: pd.DataFrame,
                    signal_type: str, lookback: int = 500) -> dict:
    """
    输入：当前K线 + 信号类型（"macd_golden_cross" / "rsi_oversold" / ...）
    输出：
    {
        "signal": "MACD金叉",
        "historical_occurrences": 23,        # 历史上出现过 23 次
        "win_rate_5d": 0.61,                 # 5日后上涨概率 61%
        "win_rate_10d": 0.52,               # 10日后上涨概率 52%
        "win_rate_20d": 0.43,               # 20日后上涨概率 43%
        "avg_return_20d": 2.3,              # 平均收益 2.3%
        "max_drawdown_20d": -8.5,           # 最差一次 -8.5%
        "confidence": "中等",               # 基于胜率分档
        "signal_decay": "该信号在10日后衰减明显"  # LLM解读
    }
    """
```

**Agent 使用**：Agent E 在收到技术报告后，终端执行 `validator.py`，把历史胜率写入交易决策中。

**决策影响**：`signal.py` 输出的「置信度」不再只是配置文件写死的值，而是基于历史统计的动态置信度。

---

### 盲区 2：多时间框架 → `scripts/multi_tf.py` + 增强 Agent C

**问题**：六家全部只用日线。但日线 MACD 金叉 + 周线 MACD 死叉 = 短期反弹而非趋势反转，这个信息全部丢失。

**方案**：Agent C 不再只分析日线，而是系统性地分析 5 个时间框架：

```
周线 (weekly)    → 趋势方向判定（主趋势）
日线 (daily)     → 交易信号判定（主要操作级别）
60分钟 (60min)   → 入场精度（精确买点）
30分钟 (30min)   → 日内验证
15分钟 (15min)   → 极端精确入场（可选）
```

**新增脚本 `multi_tf.py`**：

```python
def analyze_multi_timeframe(symbol: str,
                            daily_kline: pd.DataFrame,
                            weekly_kline: pd.DataFrame,
                            minute_60: pd.DataFrame,
                            minute_30: pd.DataFrame) -> dict:
    """
    输出：
    {
        "weekly": {"trend": "上升", "macd": "金叉第3周", "ma": "多头排列"},
        "daily": {"trend": "震荡", "macd": "死叉第5日", "rsi": "42(中性)"},
        "60min": {"trend": "下降", "macd": "底背离"},
        "30min": {"trend": "盘整", "boll": "收窄，即将突破"},
        "alignment": "部分背离",  # LLM解读关键
        "alignment_detail": "周线看多但日线震荡，60分钟底背离可能先反弹",
        "dominant_tf": "周线",    # 主导时间框架
    }
    """
```

**数据层需求**：`get_daily_kline` 已有 + `get_minute_kline` 已有（5min/60min）。
**中间层补充**：需要新增 `get_weekly_kline(symbol)` 函数（从日线聚合而来，或在中间层实现周线 OHLCV 聚合）。

---

### 盲区 3：量化风控 → `scripts/risk_quant.py` + 新增 Agent H

**问题**：六家 skill 的「风控」就是 ATR 止损 + 仓位建议。没有 VaR、没有回撤分布、没有压力测试。

**方案**：新增 **Agent H（量化风控师）**，专职风险量化。

**新增脚本 `risk_quant.py`**：

```python
def compute_risk_metrics(kline_df: pd.DataFrame,
                         benchmark_df: pd.DataFrame = None) -> dict:
    """
    输出：
    {
        "var_95_1d": -3.8,        # 95%置信度下，单日最大亏损 3.8%
        "var_99_1d": -7.2,        # 99%置信度下，单日最大亏损 7.2%
        "cvar_95_1d": -5.1,       # 条件VaR（尾部平均）
        "max_drawdown": -28.5,    # 近3年最大回撤
        "max_drawdown_duration": 94,  # 最长回撤修复天数
        "volatility_annual": 0.35,    # 年化波动率
        "beta": 1.12,             # 相对沪深300 Beta
        "beta_stability": "稳定",  # Beta 稳定性
        "drawdown_distribution": {    # 回撤分布
            "p50": -3.2,
            "p75": -8.5,
            "p90": -15.3,
            "p95": -21.0,
        },
        "stress_test": {              # 简单压力测试
            "market_down_10pct": -12.3,   # 大盘跌10%，个股预计跌12.3%
            "market_down_20pct": -24.1,
            "liquidity_crisis": -18.5,    # 流动性危机场景
        },
        "risk_budget": {
            "suggested_position_95var": 0.26,  # 基于VaR的建议仓位
            "suggested_position_99var": 0.14,
        }
    }
    """
```

**Agent H 职责**：
1. 终端执行 `risk_quant.py` 获取量化风险指标
2. 解读风险指标含义（「VaR 7.2% 意味着每 100 个交易日有 1 天可能亏超过 7.2%」）
3. 基于风险预算修正 Agent E 的仓位建议
4. 输出极端场景下的损失预估

**这补齐了六家最大的共同盲区**：没有量化风控，所有「建议」都是裸奔。

---

### 盲区 4：宏观锚定 → 新增 Agent G + 中间层 `get_macro_indicators()`

**问题**：六家都提「宏观」，但没有任何宏观数据接入。「宏观利好」是 LLM 基于新闻标题猜的。

**方案**：新增 **Agent G（宏观经济学家）**，用真实宏观数据做判断。

**中间层新增函数 `get_macro_indicators()`**（需建设）：

```python
def get_macro_indicators() -> dict:
    """
    返回：
    {
        "cpi": {"latest": 0.3, "yoy": 0.8, "trend": "温和"},
        "pmi_manufacturing": {"latest": 49.5, "trend": "连续2月低于荣枯线"},
        "pmi_services": {"latest": 51.2, "trend": "扩张"},
        "lpr_1y": 3.10,      # 1年期LPR
        "lpr_5y": 3.60,      # 5年期LPR
        "social_financing": {"latest": 18500, "yoy_growth": 8.3},  # 社融(亿)
        "credit_spread": 0.85,  # AA级信用利差
        "shibor_1y": 2.15,
        "usd_cny": 7.25,
        "data_date": "2026-06-13",
    }
    """
```

**Agent G 职责**：
1. 基于宏观数据判断经济周期位置（复苏/过热/滞胀/衰退）
2. 对目标股票所在行业做宏观敏感性分析
3. 产出「宏观对这只股票是顺风还是逆风」的结论
4. 标注宏观不确定性因素

---

### 盲区 5：业绩预期差 → 增强 Agent B + `scripts/earnings_surprise.py`

**问题**：`get_profit_forecast_eps` 返回机构预测 EPS，但无人对比「预测 vs 实际」。

**方案**：`earnings_surprise.py` + 财务中间层对接。

```python
def compute_earnings_surprise(symbol: str,
                               forecast: dict,     # get_profit_forecast_eps 输出
                               actuals: dict) -> dict:  # 财务中间层 get_financial_indicators
    """
    输出：
    {
        "latest_quarter": "2026Q1",
        "forecast_eps": 5.20,
        "actual_eps": 5.45,
        "surprise_pct": 4.8,            # 超预期 4.8%
        "surprise_direction": "beat",   # beat / miss / inline
        "historical_beat_rate": 0.75,   # 过去8季，75%超预期
        "market_reaction_typical": "+1.2%",  # 历史上超预期后平均涨幅
        "guidance_change": "上调",       # 发布后机构上调/下调/不变
    }
    """
```

**Agent B 的增强**：基本面报告不再只是「盈利预测 FY1=5.2」，而是「FY1 预测 5.2，但上季实际 5.45（超预期），且历史 75% 超预期，管理层有保守倾向」。

---

### 盲区 6：板块轮动时间序列 → 增强 Agent A + `scripts/rotation.py`

**问题**：Wind 有主线识别（单点快照），但不知道「AI 主线走了多久、是第几天还是第几周」。

**方案**：`rotation.py` 接入板块历史排名数据。

```python
def analyze_rotation(board_spot_history: pd.DataFrame) -> dict:
    """
    输入：过去 N 日的 get_board_spot("industry") 数据
    输出：
    {
        "current_leaders": ["半导体", "AI", "光模块"],
        "leader_duration": {"半导体": 5, "AI": 8, "光模块": 3},  # 连续领先天数
        "rotation_speed": 0.42,   # 轮动速度（高=快轮动，低=抱团）
        "rotation_phase": "主线强化",  # 扩散/强化/轮动/退潮
        "emerging_themes": ["液冷", "HBM"],    # 正在冒头的新方向
        "fading_themes": ["光伏", "锂电"],     # 正在退潮的老方向
        "sector_correlation": 0.78,  # 板块间相关性（高=系统性行情，低=结构性行情）
    }
    """
```

**中间层需求**：需要在数据采集阶段不只取当天的 `get_board_spot`，而是取近 10-20 个交易日的板块排名数据。可以在主 Agent Step 0 中循环调用，或在中间层新增 `get_board_spot_history(days=20)` 函数。

---

### 盲区 7 & 8：机构追踪 + 极端压力 → 已由 Agent H 和 Agent D 覆盖

- 机构持仓变化追踪 → 增强 Agent D 的 context 中纳入机构持仓季度变化数据
- 中间层需求：`get_fund_holders` 已有但需增强为「季度变化趋势」

---

### 盲区 9：产业上下游 → 增强 Agent B

**方案**：Agent B 的基本面报告中新增「产业位置」分析段。

基于 `get_company_profile` 的主营描述 + LLM 的行业知识判断：
- 公司在产业链中的位置（上游/中游/下游）
- 主要上游成本项和下游客户群
- 关键外部变量（如锂矿价格→宁德时代成本端）

这不是纯数据对接，而是 LLM 推理的强项（行业知识+公司描述→产业链位置），但需要 agent brief 中有明确指令。

---

### 盲区 10：可转债/衍生品 → 增强 Agent D

**方案**：中间层新增 `get_convertible_bond_info(symbol)` 函数。

```python
def get_convertible_bond_info(symbol: str) -> dict:
    """
    返回：
    {
        "has_convertible": True,
        "cb_code": "123456",
        "cb_price": 125.30,
        "conversion_price": 180.00,
        "conversion_premium": -5.2,  # 负溢价=套利空间
        "cb_volume": 8500,           # 成交量(万元)
        "cb_signal": "负溢价，可能有下行预期"
    }
    """
```

可转债的折溢价是正股走势的重要先行指标——这个信号六家全部忽略。

---

## 三、完整工具层：新 scripts 清单

| # | 脚本 | 功能 | 来源 | 使用者 | 状态 |
|---|------|------|------|--------|:--:|
| 1 | `ta.py` | 技术指标计算 (MACD/RSI/KDJ/BOLL/ATR/MA/K线形态) | 继承 geek | Agent C | ✅ 待写 |
| 2 | `scorer.py` | 多维度评分 (择时/估值/趋势/入场/基本面) | 继承 biga | B/C/E | ✅ 待写 |
| 3 | `signal.py` | 三信号交叉决策矩阵 | 继承 biga | E | ✅ 待写 |
| 4 | `theme_detector.py` | 主线识别数据化 | 继承 Wind | A | ✅ 待写 |
| 5 | `screener.py` | 多因子选股 | 继承 niuniu | (选股场景) | 可选 |
| 6 | **`validator.py`** 🆕 | 历史信号胜率验证 | **创新** | E | **盲区1** |
| 7 | **`multi_tf.py`** 🆕 | 多时间框架分析 | **创新** | C | **盲区2** |
| 8 | **`risk_quant.py`** 🆕 | 量化风控 (VaR/回撤/压力测试) | **创新** | H | **盲区3** |
| 9 | **`earnings_surprise.py`** 🆕 | 业绩预期差计算 | **创新** | B | **盲区5** |
| 10 | **`rotation.py`** 🆕 | 板块轮动追踪 | **创新** | A | **盲区6** |

**总计**：5 个继承 + 5 个创新 = 10 个 Python 工具脚本。

---

## 四、中间层补齐清单

Agent 能做到什么程度，取决于中间层能提供什么数据。

| # | 函数 | 用途 | 服务于 | 优先级 |
|---|------|------|--------|:--:|
| 1 | 财务中间层 8 函数搬迁 | 三张表+业绩预告+分红+预约披露 | Agent B | 🔴 立即 |
| 2 | `get_weekly_kline(symbol)` | 周线 OHLCV | Agent C (多周期) | 🟡 高 |
| 3 | `get_macro_indicators()` | CPI/PMI/LPR/社融/利差 | Agent G | 🟡 高 |
| 4 | `get_insider_trades(symbol)` | 高管增减持 | Agent D | 🟡 高 |
| 5 | `get_institutional_flow_change(symbol)` | 机构持仓季度变化 | Agent D | 🟢 中 |
| 6 | `get_convertible_bond_info(symbol)` | 可转债信息 | Agent D | 🟢 中 |
| 7 | `get_board_spot_history(days=20)` | 板块排名时间序列 | Agent A (轮动) | 🟢 中 |
| 8 | `get_industry_financial_aggregates(board)` | 行业财务中位数 | Agent B | 🟢 中 |
| 9 | `get_analyst_rating_changes(symbol)` | 分析师评级调整 | Agent B | 🔵 低 |
| 10 | `get_news_sentiment(symbol)` | 新闻情绪评分 | Agent D | 🔵 低 |

**第一批（必须）**：财务中间层 8 函数。Agent B 的深度被财务数据完整度直接制约。

**第二批（高优先）**：`get_weekly_kline` + `get_macro_indicators` + `get_insider_trades`。这三个直接支撑新增 Agent G 和 Agent C 的核心能力。

---

## 五、增强版 Agent 团队详解

### 新增 Agent G：宏观经济学家

```
┌─────────────────────────────────────────────────────────────┐
│ 角色：宏观经济学家，10 年宏观策略研究经验                      │
│ 职责：从宏观数据判断经济周期位置，评估对目标股的宏观环境       │
│                                                             │
│ 输入：data_package.macro（CPI/PMI/LPR/社融/利差/汇率）      │
│ 可用工具：terminal, file                                    │
│                                                             │
│ 分析框架：                                                   │
│  1. 增长-通胀矩阵定位（复苏/过热/滞胀/衰退）                  │
│  2. 货币政策方向（紧/中性/松）+ 信用环境                     │
│  3. 外部环境（汇率/中美利差/外资流向）                       │
│  4. 宏观→行业映射（目标股票所在行业对宏观变量的敏感度）       │
│  5. 宏观风险点（未来 1-3 月关键宏观事件）                    │
│                                                             │
│ 输出：macro_report.md                                        │
│   ├─ 经济周期位置 + 数据支撑                                 │
│   ├─ 货币政策/信用环境                                       │
│   ├─ 对该股的宏观影响（顺风/中性/逆风）                      │
│   └─ 宏观风险事件日历                                        │
└─────────────────────────────────────────────────────────────┘
```

### 新增 Agent H：量化风控师

```
┌─────────────────────────────────────────────────────────────┐
│ 角色：量化风控师，精通风险管理模型                             │
│ 职责：量化所有风险维度，修正交易策略的风险敞口                  │
│                                                             │
│ 输入：P1 全部报告 + data_package.stock.kline                │
│ 可用工具：terminal (执行 risk_quant.py), file               │
│                                                             │
│ 分析流程：                                                   │
│  1. terminal 执行 risk_quant.py → 全部风险指标               │
│  2. 解读 VaR/CVaR 的实际含义                                 │
│  3. 基于回撤分布修正止损位（ATR止损 vs 历史回撤止损取较大者） │
│  4. 基于 VaR 修正仓位建议                                    │
│  5. 输出极端场景压力测试结果                                  │
│  6. 给出风险预算：最大可接受亏损下建议仓位                     │
│                                                             │
│ 输出：risk_report.md                                         │
│   ├─ VaR/CVaR/波动率/回撤分布                                │
│   ├─ 压力测试三场景                                          │
│   ├─ 仓位修正建议                                            │
│   ├─ 止损修正建议                                            │
│   └─ 一句话风险结论                                          │
└─────────────────────────────────────────────────────────────┘
```

### 增强 Agent C：多时间框架技术分析师

在原基础上增加：
- `multi_tf.py` 终端执行 → 五周期共振/背离分析
- 周线趋势判定作为主趋势锚
- 60 分钟线作为入场精度工具
- 输出中新增「多周期一致性」判断

### 增强 Agent B：全维基本面分析师

在原基础上增加：
- `earnings_surprise.py` 终端执行 → 预期差分析
- 产业链位置判断（LLM 推理）
- 机构评级变化趋势
- 输出中新增「预期差」和「产业位置」段

### 增强 Agent D：深度资金博弈师

在原基础上增加：
- 机构持仓季度变化（如有中间层数据）
- 高管增减持解读
- 可转债信号（如有中间层数据）
- 输出中新增「机构行为」和「衍生品信号」段

### 增强 Agent E：历史验证交易策略师

在原基础上增加：
- `validator.py` 终端执行 → 信号历史胜率
- 输出中新增「历史验证」段
- 置信度从固定值变为动态历史统计

### 增强 Agent F：首席综合官

在原基础上增加：
- **盲区标注**：明确标注报告中「数据不足以判断」的部分
- 基于 Agent H 的风险报告做最终风控裁决
- 基于 Agent G 的宏观报告做宏观一致性检查
- 置信度评级从主观判断变为多维度加权

---

## 六、执行流程（4 阶段）

```
时间轴 ──────────────────────────────────────────────────────→

[t=0]   Step 0: 主 Agent 数据采集 (8-12s，因新增宏观+轮动数据)
        ├─ 加载 a-share-market skill
        ├─ 调用中间层：行情/财务/资金/板块 + get_macro_indicators
        ├─ 循环取近20日板块排名数据（轮动分析用）
        └─ 产出 data_package (JSON)

[t=12]  Step 1: 并行深度分析 (30-45s)
        ├─ Agent A: 市场+主线+轮动     → market_report.md
        ├─ Agent B: 财务+估值+预期差    → fundamental_report.md
        └─ Agent C: 技术+多周期+形态    → technical_report.md

[t=14]  Step 1b: 宏观分析 (20-30s，紧接P1启动)
        └─ Agent G: 宏观周期+敏感性     → macro_report.md

[t=45]  Step 2: 并行交叉分析 (25-40s)
        ├─ Agent D: 资金+机构+衍生品    → flow_report.md
        ├─ Agent E: 信号+历史验证+交易   → trade_signal.md
        └─ Agent H: VaR+回撤+压力测试   → risk_report.md

[t=85]  Step 3: 首席综合 (35-55s)
        └─ Agent F: 交叉质证+矛盾裁决+最终报告

[t=140] 输出：最终分析报告

总耗时：约 2.5 分钟（P1缩短因G并行启动，P2增到3并行）
```

**并行优化点**：P1b (Agent G) 在 P1 派发后立即派发，不等待 P1 完成。G 只用宏观数据，不依赖 A/B/C 的报告。这个设计让 G 的实际耗时被 P1 的最长 Agent 覆盖，不增加总时间。

---

## 七、六家继承 vs 创新对照

| # | 能力维度 | 继承来源 | 六家做到的 | 我们的增强 🆕 |
|---|---------|---------|-----------|-------------|
| 1 | 主线识别 | Wind | 单点快照 | + 轮动时间序列(rotation.py) |
| 2 | 技术分析 | geek + cn-stock | 日线单周期 | + 五周期共振(multi_tf.py) |
| 3 | 择时评分 | biga | 四维打分 | + 历史胜率验证(validator.py) |
| 4 | 信号决策 | biga | 三信号交叉 | + 动态置信度(统计驱动) |
| 5 | 基本面 | chris3cano + cn-stock | 财务+估值 | + 预期差(earnings_surprise.py) + 产业链 |
| 6 | 估值框架 | cn-stock-analyst | 成长/价值分档 | + 行业中位数动态基准 |
| 7 | 资金博弈 | chris3cano | 资金+龙虎榜 | + 机构追踪 + 可转债信号 |
| 8 | 风控 | biga (ATR止损) | 单指标止损 | + VaR/回撤锥/压力测试(risk_quant.py) |
| 9 | 宏观 | — (六家都缺) | 口头提「宏观」无数据 | + Agent G + get_macro_indicators |
| 10 | 多Agent架构 | — (六家都单线程) | 一个模型跑完 | + 8 Agent 并行协作 |
| 11 | 团队质证 | — (六家都缺) | 无矛盾检测 | + Agent F 交叉质证 + 盲区标注 |

---

## 八、实现路线

### Phase 0：补齐中间层（优先）
1. 财务中间层 8 函数搬迁 → Agent B 的 80% 数据依赖
2. `get_weekly_kline` → Agent C 的多周期分析
3. `get_macro_indicators` → Agent G 的存在前提

### Phase 1：核心计算工具（10 脚本）
1. `ta.py` + `scorer.py` + `signal.py`（继承三家）
2. `validator.py` + `multi_tf.py`（创新：历史+多周期）
3. `risk_quant.py` + `earnings_surprise.py` + `rotation.py`（创新：风控+预期差+轮动）
4. `theme_detector.py` + `screener.py`（继承 Wind + niuniu）

### Phase 2：Agent 简报 + 调度
1. 8 份 agent brief 文档（references/agent-X-brief.md）
2. SKILL.md 调度逻辑（Step 0→1→1b→2→3）
3. 端到端联调测试

### Phase 3：增强迭代
1. `get_insider_trades` / `get_convertible_bond_info` 等第二批中间层
2. Agent D 和 Agent B 的深度增强
3. 实际场景验证
