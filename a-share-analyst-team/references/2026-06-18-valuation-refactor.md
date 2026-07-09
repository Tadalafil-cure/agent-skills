# 2026-06-18 估值比较模块重构验证记录

## 变更概要

### 行情中间层 (a_share_market_middleware)

| 变更 | 文件 | 说明 |
|------|------|------|
| 改名 | `stock/comparison.py` | `get_industry_valuation` → `get_industry_valuation_comparison` |
| 降级 | `stock/comparison.py` | `get_valuation_comparison` 从 `__init__.py` 导出中移除，保留为内部函数 |
| 修复 | `stock/comparison.py:121-122` | `get_scale_comparison` 字段映射：`SECURITY_CODE` → `CORRE_SECURITY_CODE` |
| 增强 | `stock/comparison.py` | 双档统计：`meta.full` + `meta.selected`，含 `count_profitable/count_loss/count_no_pe/pe_scope` |
| 增强 | `stock/comparison.py` | 同行列表 EM 优先，PAE 备源，标注 `meta.peer_source` |
| 配套 | `__init__.py`, `comparison.py` (shim) | 导出改名 |

### 财务中间层 (a_share_finance_middleware)

| 变更 | 文件 | 说明 |
|------|------|------|
| 标注 | `finance.py:430` | TODO: `get_dupont_comparison`/`get_growth_comparison` 待财务层重构时降为内部 |

### a-share-analyst-team

| 变更 | 文件 | 说明 |
|------|------|------|
| 修复 | `data_collection.py:88` | import `get_valuation_comparison` → `get_industry_valuation_comparison` |
| 修复 | `data_collection.py:202` | 调用改名 |
| 修复 | `data_collection.py:370` | Baostock stdout 污染：`os.dup2` 重定向 |
| 更新 | `agent-b1-brief.md` | 数据描述 + 输出字段适配新结构 |
| 更新 | `agent-p-brief.md` | 自动适配（sed） |

## 端到端验证 (2026-06-18, 600519)

```
耗时: 53.2s
data_package: 6.2MB
全部 12 个 stock 字段 success=True

估值:
  board=白酒Ⅱ, peer_source=em
  full: total=19, profitable=15, loss=4, no_pe=0
  full PE: mean=49.88, median=25.0, scope=仅覆盖盈利企业 (PE>0)
  selected: codes=['600519','000858','603198','600559','600779','600702'], count=6, profitable=6
  selected PE: mean=38.96, median=24.44

龙虎榜/大宗/股东户数/质押: 全部 success=True
```

## 估值 meta 新结构速查

```python
r = get_industry_valuation_comparison("300394")
m = r["meta"]

m["board"]           # "通信设备"
m["peer_source"]      # "em" (主源) | "pae" (备源)

# 全量
f = m["full"]
f["count"]            # 87 (同行总数)
f["count_profitable"] # 62 (盈利家数, PE>0)
f["count_loss"]       # 25 (亏损家数, PE≤0)
f["count_no_pe"]      # 0  (无PE数据)
f["pe_scope"]         # "仅覆盖盈利企业 (PE>0)"
f["pe_ttm_mean"]      # 334.69
f["pe_ttm_median"]    # 113.86
f["pe_ttm_min"]       # 15.8
f["pe_ttm_max"]       # 7648.12
f["pb_mean"]          # ...
f["pb_median"]        # ...

# 精选6家
s = m["selected"]
s["codes"]            # ['300394','002396','603083','300308','601869','300502']
s["count"]            # 6
s["count_profitable"] # 6
s["pe_ttm_mean"]      # 150.33
s["pe_ttm_median"]    # 128.75
```

## 数据流

```
get_industry_valuation_comparison(symbol)
  ├─ 主源: get_scale_comparison(symbol)  → 板名 + 同行代码 (EM, CORRE_* 字段)
  ├─ 备源: symbol_to_board(symbol)       → 板名 + 同行代码 (PAE)
  ├─ TX batch(同行代码)                   → PE/PB (腾讯 qt.gtimg.cn)
  └─ stock_zh_valuation_comparison_em    → 精选6家代码 (EM, 内部调用)
```
