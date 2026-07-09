# 字段速查表（由实际返回值提取，非手写）

> 所有中间层函数返回 `{"success": bool, "data": ..., "source": str, "meta": {...}}`
> 此表列 `data` 和 `meta` 的字段名。字段名即代码中使用的 key，**不需要翻译或映射**。

## 市场指数层 (overall/)

### get_index_quotes()
- data 类型：`dict[str, dict]` — key 是 6 位指数代码
- 每条 data[code] 字段：
  `指数名称` `代码` `最新价` `昨收` `今开` `最高` `最低` `涨跌幅` `涨跌额` `成交量` `成交额` `振幅` `5日涨跌幅` `10日涨跌幅` `20日涨跌幅` `60日涨跌幅` `120日涨跌幅` `年初至今涨跌幅`

### get_market_breadth()
- data[0] 字段：`日期` `上证收盘` `20日新高` `20日新低` `60日新高` `60日新低` `120日新高` `120日新低`
- meta 关键字段：`latest_date` `latest_high20` `latest_low20`

### get_market_congestion()
- data[0] 字段：`日期` `上证收盘` `拥挤度` `top5Amount` `totalAmount` `congestionPercent`
- meta：`latest_date` `latest_congestion`

### get_ebs()
- data[0] 字段：`日期` `沪深300指数` `股债利差` `dvSpread` `dvTtmSpread` `股债利差均线`
- meta：`latest_date` `latest_hs300` `latest_ebs` `latest_ebs_ma`

### get_buffett_index()
- data[0] 字段：`总市值` `GDP` `日期` `巴菲特指数`
- meta：`latest_date` `latest_buffett` `latest_marketcap` `latest_gdp` `pct_all` `pct_10y`
- pct_all / pct_10y 结构：`{"value": 0.9347, "range": "2005-04-08 ~ 2026-06-16"}`

### get_northbound_flow()
- data[0] 字段：`date` `northMoney` `southMoney` `amountHongKongToSH` `amountHongKongToSZ` `amountSHToHongKong` `amountSZToHongKong`
- ⚠️ 北向成交额字段是 `northMoney`，不是 `net_flow_north`

### get_margin_summary()
- data[0] 字段：`日期` `融资余额` `融券余额` `融资买入额` `融券卖出量`
- meta：`actual_date`

## 行业板块层 (sector/board.py)

### get_board_spot("industry")
- data 字段：`板块名称` `板块代码` `股票数` `涨跌幅` `涨跌额` `涨速` `换手率` `市盈率` `成交量` `成交额` `总市值` `当前价` `昨收` `上涨家数` `下跌家数` `领涨股` `领跌股`

### get_board_fund_flow("industry")
- data 字段：`板块名称` `板块代码` `板块级别` `主力净流入` `主力流入` `主力流出` `总成交额`

## 概念板块层 (sector/concept.py)

### get_concept_spot()
- data 字段：`板块名称` `板块代码` `当前价` `昨收` `涨跌幅` `涨跌额` `股票数` `上涨家数` `下跌家数` `领涨股` `领跌股`

### get_board_fund_flow("concept")
- data 字段：`板块名称` `板块代码` `板块级别` `主力净流入` `主力流入` `主力流出` `总成交额`

---

## 个股估值层 (stock/comparison.py)

### get_industry_valuation_comparison(symbol)
- 数据源：TX batch（全量 PE/PB）+ akshare 精选6家代码
- data 类型：`list[dict]` — 全行业同行估值列表（按 PE 升序）
- data[i] 字段：`代码` `简称` `最新价` `涨跌幅` `市盈率-TTM` `市净率` `总市值` `流通市值` `换手率`
- meta 结构：
  - `board`: 行业名，如 "通信设备"
  - `peer_source`: 同行列表来源 `"em"`（主源）或 `"pae"`（备源）
  - `full`: `{count, count_profitable, count_loss, count_no_pe, count_with_pb, pe_scope, pe_ttm_mean, ...}`
  - `selected`: `{codes, count, count_profitable, count_loss, count_no_pe, count_with_pb, pe_scope, pe_ttm_mean, ...}`
- ⚠️ `pe_scope` = "仅覆盖盈利企业 (PE>0)"，PE 均值/中位**不含**亏损和缺失企业
- `count` = 同行总数，`count_profitable` = 盈利家数，`count_loss` = 亏损家数，`count_no_pe` = 无 PE 数据

### get_valuation_comparison(symbol) [内部—akshare 8行]
- data 类型：`list[dict]` — ⚠️ **是 list！取 `data[0]`**
- data[0] 字段：`排名` `代码` `简称` `PEG` `市盈率-TTM` `市销率-24A` `市销率-TTM` `市净率-24A` **`市净率-MRQ`** `市现率1-24A` `市现率1-TTM` `市现率2-24A` `市现率2-TTM` `EV/EBITDA-24A` `市盈率-FY1` `市盈率-FY2` `市盈率-FY3` `市销率-FY1` `市销率-FY2` `市销率-FY3`
- meta：`rows` `cols` `columns` `fy_map`（{FY1:"2026E", FY2:"2027E", FY3:"2028E"}）
- ⚠️ PB 字段是 `市净率-MRQ`，不是 `市净率`

## 个股研究层 (stock/research.py)

### get_profit_forecast_eps(symbol)
- data 类型：`list[dict]` — ⚠️ **是 list！**
- data[0] 字段：`年度` `预测机构数` `EPS最小值` **`EPS均值`** `EPS最大值` `行业平均EPS`
- ⚠️ EPS 字段是 `EPS均值`，不是 `FY1_EPS`

## 个股资金层 (stock/flow.py)

### get_individual_fund_flow(symbol)
- data 类型：`list[dict]` — ⚠️ **是 list！取 `data[0]`**
- data[0] 字段：`代码` `简称` **`当日主力净流入`** `当日净占比` `近5日主力净流入` `近5日净占比`
- ⚠️ 资金字段是 `当日主力净流入`，不是 `主力净流入`
- ⚠️ 单位是**元**（不是亿），需 `/1e8` 转换

---

## 排序取 Top/Bottom 范式

```python
# ✅ 正确：直接用中文字段名
sorted_data = sorted(data, key=lambda x: x.get('涨跌幅', 0) or 0, reverse=True)
top5 = sorted_data[:5]
bot5 = sorted_data[-5:]

# ❌ 错误：用臆想的英文名
sorted(data, key=lambda x: x.get('changePct', 0))  # 不存在！
```
