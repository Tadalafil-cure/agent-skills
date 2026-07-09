# 行业估值管线：EM / PAE / TX 三源协作

`get_industry_valuation_comparison(symbol)` 的数据流和演进备忘。

## 数据流

```
get_industry_valuation_comparison("300394")
  │
  ├─① 同行代码（主源 EM，备源 PAE）
  │   get_scale_comparison(symbol)  → board="通信设备" + CORRE_* 代码列表
  │   └─ fallback: symbol_to_board  → PAE get_board_cons
  │
  ├─② 精选6家（EM akshare）
  │   stock_zh_valuation_comparison_em → 6 只精选股代码
  │
  ├─③ 批量估值（TX）
  │   get_realtime_quote_batch([全量+精选]) → PE/PB/市值
  │
  └─④ 双档统计
      meta.full     → 全行业均值/中位（仅盈利企业 PE>0）
      meta.selected → 精选6家均值/中位（TX 基数，非 akshare MRQ）
```

## 三源分工

| 源 | 角色 | 贡献 |
|----|------|------|
| **EM** (东方财富 datacenter) | 主源 | 行业名 + 同行代码列表（RPT_PCF10_INDUSTRY_MARKET）+ 精选6家代码 |
| **PAE** (百度) | 备源 | 同行代码列表（EM 挂了时用） |
| **TX** (腾讯 qt.gtimg.cn) | 估值基数 | 实时 PE-TTM / PB / 市值（批量一次请求） |

## EM API 字段陷阱

EM datacenter API 返回的每一行都有两套字段：

```
SECUCODE=600519.SH  SECURITY_CODE=600519  SECURITY_NAME_ABBR=贵州茅台
CORRE_SECUCODE=000858.SZ  CORRE_SECURITY_CODE=000858  CORRE_SECURITY_NAME=五粮液
```

- `SECURITY_CODE` / `SECURITY_NAME_ABBR` — **永远是目标股自身**（filter 里传的那个）
- `CORRE_SECURITY_CODE` / `CORRE_SECURITY_NAME` — **才是同行股票**

**错误**：把 `SECURITY_CODE` 映射为 `代码` → 所有行代码全是 600519（23 行重复）
**正确**：把 `CORRE_SECURITY_CODE` 映射为 `代码` → 每行是不同的同行

`get_scale_comparison` 已在 2026-06-17 修正此映射。

## PE 统计标注规范

meta.full 和 meta.selected 必须包含：

| 字段 | 含义 |
|------|------|
| `count` | 同行总数 |
| `count_profitable` | 盈利家数（PE>0，参与统计） |
| `count_loss` | 亏损家数（PE≤0，排除） |
| `count_no_pe` | 无 PE 数据 |
| `pe_scope` | `"仅覆盖盈利企业 (PE>0)"` |

不允许出现模糊的 `count_with_pe=61/86` 而不标注亏损家数。

## 双档设计

精选6家 PE/PB 用 TX 基数重算，不与 akshare 的 MRQ-PB 混用。保证全量和精选可比：

```
akshare 精选 PB: 市净率-MRQ（最近季报净资产）
TX 全量 PB:     市净率（实时价格/净资产）
→ 不可比

TX 精选 PB:     市净率（实时价格/净资产）
TX 全量 PB:     市净率（实时价格/净资产）
→ 可比 ✓
```
