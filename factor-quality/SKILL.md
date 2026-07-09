---
name: factor-quality
description: A股因子质量分析引擎 —— 独立前置模块。按指数面板评估因子有效性（IV/PSI/IC/相关性），输出排名报告供 a-share-analyst-team Agent 引用。不修改任何现有工作流。
trigger: 
  - 每次 A 股深度分析前（Agent brief 自动引用）
  - cron 盘后更新指数面板
  - 手动 "更新因子质量" / "检查因子有效性"
tags: [a-share, factor-analysis, quantitative, panel-data]
version: 0.1.0
---

# factor-quality · A股因子质量分析引擎

独立前置模块。与 a-share-analyst-team 零耦合。

## 核心理念

**指数面替代行业面**：因子质量测的是量价行为，共性由规模和流动性决定。
- 沪深300（大盘蓝筹）的因子行为高度一致
- 白酒行业（1.8万亿茅台 + 80亿金徽酒）反而分化

## 因子清单（14个，全从OHLCV计算）

ma20_div / ma5_ma20_ratio / rsi14 / macd_hist / macd_dif_dea_gap / kdj_k / kdj_j / boll_position / boll_bandwidth / vol_ratio / adx / atr_pct / ret_5d / ret_20d

## 统计方法

### IV（10箱等频分箱 → WOE → Σ(good%−bad%)×WOE）
IV<0.02 弱 / 0.02~0.1 中 / 0.1~0.3 强 / >0.3 极强

### PSI（时间等分三份 → 以早期为基准）
PSI<0.1 稳定 / 0.1~0.25 轻微漂移 / >0.25 不稳定

### Spearman IC（秩相关 | 因子值排序 vs 30日收益方向）
|IC|<0.03 无效 / 0.03~0.05 弱 / >0.05 有效

### 相关性去重（Pearson r → |r|≥0.7 → 保留IV高者）

### 综合评级
★★★★★: IV≥0.1+PSI<0.1+|IC|>0.05 / ★★★: IV≥0.02+PSI<0.25+|IC|>0.03 / ★★: IV≥0.02+PSI≥0.25 / ★: IV<0.02

### 三套输出方案

| 方案 | 条件 | 适用 Agent |
|:--|:--|:--|
| 去冗余 | IV≥0.02 + PSI<0.25 + 去¦r¦≥0.7 | C1趋势、D资金（信息互补） |
| 高区分 | IV≥0.10 + PSI<0.25 + 去¦r¦≥0.7 | C2反转、E策略（只盯最强2-3个） |
| 稳定优先 | IV≥0.01 + PSI<0.10 + 去¦r¦≥0.7 | 线上部署（换股票也稳，排除纯噪声） |

## 覆盖指数

| 指数 | 代码 | 成分股 | 策略 |
|:--|:--|:--:|:--|
| 沪深300 | 000300 | 300 | 全量 |
| 中证500 | 000905 | 500 | 抽样300 |
| 科创50 | 000688 | 50 | 全量 |
| 创业板指 | 399006 | 100 | 全量 |
| 中证1000 | 000852 | 1000 | 抽样300 |
| 中证A500 | 000510 | 500 | 抽样300 |

## 调度

定时(cron盘后) `python factor_quality.py --update-panels` → data/panels/
惰性(个股分析时) 检查 data/stocks/{code}.json → ≤30天直接读 → >90天重跑

## 与 A-team 接触面

Agent brief 加因子质量引用段（≤3行），读取 data/panels/{指数}.json。
不改 data_collection.py、任何脚本、任何 Agent 主逻辑。

## 硬约束

1. 不改 A-team 任何文件
2. 中间层优先：K线用 get_daily_kline
3. 算推分离：IV/PSI/IC 全机械计算，阈值 if-else，零 LLM
4. 个股惰性：不预跑全市场
5. 失败不阻断：文件缺失时 Agent 正常分析
