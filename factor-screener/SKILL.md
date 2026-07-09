---
name: factor-screener
description: 多因子选股筛选器 —— 拿 factor_quality 的因子质量结论训练 XGBoost 模型，从股票池产出排序推荐。量化初筛后交 A-team 深析。
status: reserved
version: 0.0.0
---

# factor-screener · 多因子选股筛选器（预留）

> 状态：预留空间。等 factor_quality 积累足够面板数据后启用。

## 定位

```
factor_quality → 有效因子 + 面板数据 → XGBoost 训练 → 选股排序
                                                 ↓
                                          A-team 深析 TOP N
```

## 依赖

- factor_quality：指数面板 + 个股时序因子质量
- 中间层：K线 / 资金流 / 估值数据
- 选股回测记录积累（≥6个月）

## 计划路线

```
v0.1: 沪深300选股 — 单指数 XGBoost 排序
v0.2: 多指数覆盖 — 科创50 / 中证500
v0.3: 多模型对比 — Pareto 前沿（model-comparison）
v0.4: auto-experiment — 自动探索最优因子组合（四阶段：组评估→增量叠加→消融→组内筛选）
```
