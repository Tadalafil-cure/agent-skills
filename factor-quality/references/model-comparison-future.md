# model-comparison · Pareto 前沿选模（待启用）

> 状态：暂存。等 factor_quality → xgb_modeling 积累选股预测记录后启用。
> 依赖：需至少 6~12 个月选股预测回测记录。

## 用途

多套选股模型（不同因子组合 / 不同算法）在同一回测数据上对比，Pareto 前沿判定谁被支配、谁互不支配。

## 指标

| 指标 | 含义 | 计算 |
|:--|:--|:--|
| 胜率 | 选中的股票上涨的月份比例 | `sklearn` |
| 月均收益 | 等权持有收益均值 | `numpy` |
| IC | 排序分 vs 实际收益 Spearman | `scipy.stats.spearmanr` |
| ICIR | IC均值 ÷ IC标准差 | `numpy` |
| 最大回撤 | 累计净值最高→最低跌幅 | `numpy` |
| 换手率 | 每月换掉的股票比例 | `pandas` |

## Pareto 判定

```
for 模型A, 模型B in 所有模型对:
    if A在所有指标上 ≥ B 且至少一指标严格 > :
        B 被 A 支配 → B 不在前沿
    elif 互相无法支配:
        都在前沿上 → 需场景取舍（LLM 介入）

前沿模型集 = {未被任何模型支配的模型}
```

## 与 factor_quality 的关系

```
factor_quality → 有效因子 → xgb_modeling → 选股预测记录
                                              ↓
                                    model_comparison（本文件）
```

## 金工出处

DianJin-SKILLS / financial-engineering-expert / model-comparison
