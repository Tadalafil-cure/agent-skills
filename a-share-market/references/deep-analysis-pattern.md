# 深度分析工作流模板（2026-06-17 更新）

> 适用：用户要求"收盘深度分析"、"分析今天的行情 + N 只个股"

## 铁律：先验一只，再批量

**⚠️ 不要一次跑 N 只股票的所有函数。** 每只股票的函数返回结构可能不同（list vs dict vs top-level），一次全跑 → 一只报错全部白费。

正确流程：
```
1. 先跑 1 只股票的所有函数，验证数据结构
2. 确认字段名和类型无误后，再跑其余 N-1 只
3. 每批跑完立刻写盘（不要攒到最后）
```

## 数据采集：三层分批

execute_code 中执行，共 ~30-35 个函数调用，分 9 批：

### 市场层（Batch 1-4）

```
Batch 1: 市场指数 + 宽度 + 融资融券 + 北向（异构源，全部并发）
  get_index_quotes() + get_market_breadth() + get_margin_summary() + get_northbound_flow()

Batch 2: 拥挤度 + 股债利差 + 巴菲特（legulegu，≤3 OK）
  get_market_congestion() + get_ebs() + get_buffett_index()

Batch 3: 行业行情 + 概念行情（PAE，≤2）
  get_board_spot("industry") + get_concept_spot()

Batch 4: 行业资金 + 概念资金（PAE，≤2）
  get_board_fund_flow("industry") + get_board_fund_flow("concept")
```

### 个股层（Batch 5-9）

```
Batch 5: 个股实时行情（tx 源，N 只可并发）
  get_realtime_quote(sym) × N

Batch 6: 个股日 K 线（tx_http 源，N 只可并发）
  get_daily_kline(sym) × N

Batch 7: 个股资金流向（PAE 源，串行，间隔 0.6s）
  get_individual_fund_flow(sym) × N

Batch 8: 估值对比 + 盈利预测（EM 源，串行对，间隔 0.5s）
  get_industry_valuation_comparison(sym) + get_profit_forecast_eps(sym) × N

Batch 9（可选深度层）: 行业归属 + 基本面 + 研报 + 股东
  symbol_to_board(sym) + get_company_profile(sym) + get_stock_news(sym)
  + get_top10_shareholders(sym) + get_research_reports(sym)
```

写入 `/tmp/deep_analysis.json`，用 `default=str` 防 NaN 序列化崩溃。

## 分析报告结构

```
## 📊 大盘全景
表格：10 指数 今日/5日/年内 (get_index_quotes)

## 🌡️ 市场温度
- 宽度：新高/新低比 (get_market_breadth meta.latest_*)
- 拥挤度 (get_market_congestion meta.latest_congestion)
- 股债利差 vs MA (get_ebs meta.latest_*)
- 巴菲特指数 + 全历史/10Y 分位 (get_buffett_index meta + pct_all/pct_10y)
- 融资余额 + 北向成交额

## 🏭 行业结构
- 领涨 Top5 / 领跌 Bottom5 (get_board_spot)
- 资金流入 Top5 / 流出 Bottom5 (get_board_fund_flow)
- 概念 Top10 / Bottom5 (get_concept_spot)
- 一句话：资金从 X 流向 Y

## 📈 个股深度（每只）
| 指标 | 来源 | 字段路径 |
|------|------|------|
| 行业归属 | symbol_to_board | `r['board']` ← 顶层，不是 data |
| PE-TTM | get_valuation_comparison | `v['data'][0]['市盈率-TTM']` |
| PB (MRQ) | get_valuation_comparison | `v['data'][0]['市净率-MRQ']` |
| PEG | get_valuation_comparison | `v['data'][0]['PEG']` |
| PE-FY1/FY2 | get_valuation_comparison | `v['data'][0]['市盈率-FY1']/'市盈率-FY2'` |
| FY1 EPS | get_profit_forecast_eps | `e['data'][0]['EPS均值']` + `预测机构数` |
| 5/20/60日涨幅 | get_daily_kline | `k[0]/[4]/[19]/[59]` 收盘价计算 |
| 当日主力净流入 | get_individual_fund_flow | `f['data'][0]['当日主力净流入']` / 1e8 → 亿 |
| 5 日主力净流入 | get_individual_fund_flow | `f['data'][0]['近5日主力净流入']` / 1e8 → 亿 |
| 主营 | get_company_profile | `p['data'][0]['主营业务']` |
| 近期新闻 | get_stock_news | `n['data'][0]['title']` |
| 十大股东 | get_top10_shareholders | `th['data'][0]['股东名称']` + `持股比例` |
| 研报 | get_research_reports | `reps['data'][0]['title']` |

## 🧠 综合分析
- 市场格局：存量/增量，资金流向
- 风格：成长 vs 价值
- 估值水位：整体是否偏贵
- 个股排序与理由
```

## 关键坑位（按踩坑频率排序）

| # | 函数 | 错误写法 | 正确写法 |
|---|------|------|------|
| 1 | `get_valuation_comparison` | `v['data'].get('市盈率-TTM')` | `v['data'][0]['市盈率-TTM']` — **list** |
| 2 | `get_individual_fund_flow` | `f['data'].get('主力净流入')` | `f['data'][0]['当日主力净流入']` — **list** + 字段名不同 |
| 3 | `get_profit_forecast_eps` | `e['data'].get('FY1_EPS')` | `e['data'][0]['EPS均值']` — **list** + 字段名不同 |
| 4 | `symbol_to_board` | `r['data']['board']` | `r['board']` — **顶层字段**，无 data 包装 |
| 5 | `get_company_profile` | `p['data'].get('主营业务')` | `p['data'][0]['主营业务']` — **list** |
| 6 | `get_index_quotes` | `data[0]` | `data['000001']` — **dict** |
| 7 | PB 字段 | `'市净率'` | `'市净率-MRQ'` |
| 8 | 主力净流入单位 | 直接读 | `/ 1e8` → 亿（原始单位是元） |
| 9 | JSON 序列化 | 崩溃 | `default=str` 防 NaN |
| 10 | 批量跑股 | 4 只一起跑 | 先验 1 只，再跑其余 |
