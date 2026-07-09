# TX vs akshare 估值差异速查

> 对比 `get_realtime_quote_batch`（TX 实时）与 `stock_zh_valuation_comparison_em`（akshare/EM）的 PE/PB 差异。

## PE-TTM

| 数据源 | 计算方式 | 差异 |
|--------|---------|:--:|
| TX (`市盈率-TTM`, f[39]) | 交易所实时 PE-TTM | ±2% |
| akshare (`市盈率-TTM`) | 同源（交易所实时） | ±2% |

**结论：PE-TTM 基本一致，差异来自微小的时间延迟。**

## 市净率 (PB)

| 数据源 | 计算方式 | 差异 |
|--------|---------|:--:|
| TX (`市净率`, f[46]) | 当日股价 / 净资产（实时推算） | 基准 |
| akshare (`市净率-MRQ`) | 当日股价 / 最近季报净资产 | **高 1-10%** |

**根因：MRQ（Most Recent Quarter）净资产比实时推算的净资产旧 1-3 个月，分母小 → PB 偏高。**

## 对行业对比的影响

- PE 排名：TX 和 akshare 结果可互换
- PB 排名：同源比较才可比。TX 全量和 akshare 精选不能直接比 PB，除非统一基数
- `get_industry_valuation_comparison` 已解决此问题：精选6家代码从 akshare 提取后用 TX 同源重算

## 何时用哪个

| 场景 | 推荐 |
|------|------|
| 行业 PE 对比 | TX batch（0.03s，全量） |
| 行业 PB 对比 | TX batch（同源可比） |
| 估值比较页面（东方财富风格） | akshare（含 PEG/PS/PCF/EV_EBITDA 等多维指标） |
| 全量+精选双档对比 | `get_industry_valuation_comparison`（一次调用，统一 TX 基数） |
