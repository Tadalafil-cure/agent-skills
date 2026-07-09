# 全量行业 PE/PB 路径

> ⚠️ **此文件描述历史路径。现在有 `get_industry_valuation_comparison(symbol)` 一键完成，无需手动两步。**
>
> 详情 → `references/valuation-pipeline.md`

`get_valuation_comparison()` 只返回 ~8 行（API 硬限，翻页无效）。要拿全行业 PE/PB：

## 旧：手动两步法（已被替代）

```python
# 第一步：拿全行业代码
r = get_scale_comparison("300394")
peers = [d['代码'] for d in r['data'] if d['代码'] not in ('行业平均','行业中值','')]

# 第二步：逐个取实时行情（含 PE/PB）→ 100 只同行需 ~50 批次
for code in peers:
    q = get_realtime_quote(code)
    pe = q['data'].get('市盈率-TTM')
    pb = q['data'].get('市净率')
```

## 新：一键调用

```python
from a_share_market_middleware.stock.comparison import get_industry_valuation_comparison

r = get_industry_valuation_comparison("300394")
# → meta.full:     全行业 PE/PB 均值/中位（86只，一次 TX batch）
# → meta.selected: 精选6家 PE/PB 均值/中位（TX 基数）
# → meta.peer_source: "em"（主源）或 "pae"（备源）
```

## 数据源演进

| 字段 | 旧路径 | 新路径 |
|------|--------|--------|
| 同行代码 | `get_scale_comparison`（EM） | 同左，EM 优先，PAE 备源 |
| PE-TTM | `get_realtime_quote` × N 次 | `get_realtime_quote_batch` × 1 次 |
| 市净率 | 同上 | 同上（TX 实时，非 akshare MRQ） |
| 精选名单 | 无 | akshare `stock_zh_valuation_comparison_em` |
