# Step 0 数据管道 DAG

> 代替 `data_collection.py` 单体脚本。
> 主 Agent 按此 DAG 分阶段派发 `delegate_task`，产出 9 个数据文件（7 个就绪 + F#8/F#9 待建）。

## 源并发规则（子 Agent 间）

| 源 | 最大并发 | 约束 |
|----|:--:|------|
| tx | 2 | tx_http 同源，合计 ≤2 |
| sina | 2 | 独立 |
| em | **2** | eastmoney API，跨子 Agent 合计 ≤2 |
| pae | 2 | 独立 |
| legulegu | 1 | 独立 |
| ft | 1 | 独立 |
| akshare | 1 | 独立 |
| bs | **1** | **严禁任何并发。跨阶段独占，同一阶段只有一个 bs 子 Agent** |

## 文件 → 消费者

```
{TASK_BASE}/data/market_data.json      →  Agent A1, A2
{TASK_BASE}/data/stock_kline.json      →  Agent C1, C2, H(1元退市)
{TASK_BASE}/data/stock_valuation.json  →  Agent B1, B2, P
{TASK_BASE}/data/stock_forecast.json   →  Agent B1, B2
{TASK_BASE}/data/stock_flow.json       →  Agent D
{TASK_BASE}/data/financial_data.json   →  Agent B1, B2, H(ST风险)
{TASK_BASE}/data/penalties.json        →  Agent H
| `factor_quality.json`   →  Agent C1, C2, C3, I, H, W
| `web_search_data.json`  →  Agent B1, B2, S, F1, F2, F

B3/C3/E3 → 只消费上游报告，不消费数据文件
F → 消费上游摘要 + web_search_data.json（搜索结果为辩论素材）
G → 数据暂缺，跳过（待 F#9 macro_data.json）

### 待就绪（中间层未到位）

| # | 文件 | 约大小 | 消费者 | 来源 | 状态 |
|---|------|--------|--------|------|:--:|
| F#1 | market_data.json     | ~50KB  | A1, A2 | tx, pae, legulegu, ft, akshare | ✅ |
| F#2 | stock_kline.json     | ~80KB  | C1, C2, H | tx, sina | ✅ |
| F#3 | stock_valuation.json | ~15KB  | B1, B2, P | em, 其他 | ✅ |
| F#4 | stock_forecast.json  | ~20KB  | B1, B2 | em | ✅ |
| F#5 | stock_flow.json      | ~40KB  | D | em, bs, 其他 | ✅ |
| F#6 | financial_data.json  | ~10KB  | B1, B2, H | bs | ✅ |
| F#7 | penalties.json       | ~5KB   | H | sina scraping | ✅ |
| F#10| factor_quality.json  | ~15KB  | C1, C2, C3, I, H, W | 本地 + TX + akshare | ✅ |
| F#11| web_search_data.json | ~15KB  | B1, B2, S, F1, F2, F | ddgs + scrapling | 🆕 v0.8.6 |
| F#8 | financial_full.json  | ~100KB | B1, B2, B3 | a-share-finance-middleware | ❌ 未就绪 |
| F#9 | macro_data.json      | ~50KB  | G | 待建 | ❌ 未建 |

F#8 内容：杜邦分析、成长对比、三表全文。届时 F#6(financial_data.json) 并入 F#8 或废弃。
F#9 内容：CPI/PMI/GDP/利率/社融等宏观指标。独立 D，bs 源或第三方。
```

## DAG

```
┌── S1：并行 5 子 Agent（无 em、无 bs）─────────────────────────┐
│                                                               │
│  [D1] F#1 market_data.json                                    │
│  源: tx×1, pae×3, legulegu×2, ft×1, akshare×1                 │
│  函数: index_quotes, breadth, activity, northbound,            │
│        margin, industry_spot, concept_spot,                    │
│        industry_flow, concept_flow                             │
│  源并发: 无冲突（各源 ≤2）                                     │
│  写出: {TASK_BASE}/data/market_data.json                             │
│                                                               │
│  [D2] F#2 stock_kline.json                                    │
│  源: tx×2, sina×2                                             │
│  函数: daily_kline, minute_kline(60),                          │
│        minute_kline(30), realtime_quote                        │
│  源并发: tx=2(safe), sina=2(safe)                              │
│  写出: {TASK_BASE}/data/stock_kline.json                             │
│                                                               │
│  [D7] F#7 penalties.json                                      │
│  源: sina scraping                                            │
│  函数: st_penalties.py --ts-code {symbol}                      │
│  源并发: 独立，无冲突                                          │
│  写出: {TASK_BASE}/data/penalties.json                               │
│                                                               │
│  [D8] F#10 factor_quality.json                                │
│  源: 本地文件 + TX + akshare（指数成分）                        │
│  函数: prepare_factor_quality.py {symbol}                       │
│  源并发: TX独立，akshare独立，无冲突                            │
│  写出: {TASK_BASE}/data/factor_quality.json                          │
│                                                               │
│  [D9] F#11 web_search_data.json                               │
│  源: ddgs + scrapling（网络搜索，与金融API无冲突）              │
│  函数: collect_web_search.py --symbol --name --industry         │
│  说明: 搜个股动态 + 行业动态，两路并行抓取                      │
│  源并发: 独立，ddgs限频时自动串行                               │
│  写出: {TASK_BASE}/data/web_search_data.json                         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
        │
        ↓  (D1+D2+D7 全部完成)
┌── S2：串行 2 子 Agent（em 独占，无 bs）───────────────────────┐
│                                                               │
│  [D3] F#3 stock_valuation.json  (先跑)                        │
│  源: em×2 + 其他×1                                            │
│  函数: industry_valuation_comparison, scale_comparison,         │
│        company_profile                                        │
│  源并发: em=2(到上限)，其他独立                                │
│  写出: {TASK_BASE}/data/stock_valuation.json                         │
│          │                                                    │
│          ↓  (D3 释放 em)                                      │
│  [D4] F#4 stock_forecast.json   (后跑)                         │
│  源: em×3                                                     │
│  函数: profit_forecast_eps, profit_forecast_metrics,            │
│        research_reports                                       │
│  源并发: em=3（单子 Agent 内部串行，安全）                     │
│  写出: {TASK_BASE}/data/stock_forecast.json                          │
│                                                               │
└───────────────────────────────────────────────────────────────┘
        │
        ↓  (D3+D4 全部完成)
┌── S3：串行 2 子 Agent（bs 独占）─────────────────────────────┐
│                                                               │
│  [D5] F#5 stock_flow.json      (先跑)                         │
│  源: em×4, bs×2, 其他×3                                       │
│  函数: individual_fund_flow(em), lhb_stat(em),                  │
│        dzjy_stat(em), fund_holders(em),                        │
│        shareholder_count(bs), top10_shareholders(bs),           │
│        shareholder_changes, margin_detail, pledge_info          │
│  注意: em 此时无其他消费者，安全；bs 必须在子 Agent 内串行       │
│  写出: {TASK_BASE}/data/stock_flow.json                              │
│          │                                                    │
│          ↓  (D5 释放 bs)                                      │
│  [D6] F#6 financial_data.json   (后跑)                         │
│  源: bs×2                                                     │
│  函数: financial_abstract, financial_indicators                 │
│  注意: bs 串行，无并发风险                                     │
│  写出: {TASK_BASE}/data/financial_data.json                          │
│                                                               │
└───────────────────────────────────────────────────────────────┘
        │
        ↓
┌── ✓ Step 0 完成 ─────────────────────────────────────────────┐
│  /tmp/data/ 下 9 个文件全部就绪（含 F#10/F#11）                │
│  → 进入 Step 1: Agent A / B1 / B2                             │
└──────────────────────────────────────────────────────────────┘
```

## 执行约束

1. 每个 D 是一个 `delegate_task` 子 Agent（工具集 `["terminal"]`）
2. 子 Agent 直接调用 `scripts/` 下的固化采集脚本，**禁止现场写临时脚本**：
   ```bash
   python3 /home/admin/agent-skills/a-share-analyst-team/scripts/collect_market.py \
     --symbol {symbol} --output {TASK_BASE}/data/market_data.json
   ```
3. 脚本路径固定，只传 `--symbol` 和 `--output`，零现场编码
4. 任一函数失败 → 标注 `{"success": false, "error": "..."}`，不阻断同文件其他函数
5. bs 源函数必须串行：每个 bs 调用后 `sleep(random.uniform(0.5, 1.0))`
6. em 源函数在子 Agent 内可并行（≤2），子 Agent 间接 em 限制由阶段编排保证
7. `st_penalties.py` 位于 skill 的 `scripts/` 目录
