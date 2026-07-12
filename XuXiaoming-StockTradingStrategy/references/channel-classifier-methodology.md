# 通道分类器方法论 · v2→v5 演进

## v5 设计原则（纯徐小明）

### 工具边界

| ✅ 徐小明在用 | ❌ 量化圈常用但徐小明没用 |
|-------------|------------------------|
| 均线通道（MA20/MA60 本身构成上下轨） | ATR 波动率收敛 |
| 双线间距收敛/发散 | ADX 定向运动 |
| 收盘价突破/破位 | Donchian/Keltner channel |
| MACD 钝化→结构（judges turning points, not direction） | Bollinger Band squeeze |

反模式 A6：塞外来指标——实现徐小明方法论时容易顺手把量化圈常用工具塞进去。这些工具徐小明原文中零出现。每次加指标前问一句："徐小明提过吗？没有就砍掉。"

### 算法核心

```python
# 通道上下轨 = 两条均线本身
upper = max(MA20, MA60)
lower = min(MA20, MA60)

# 突破 = 收盘价 > 上轨（普通情况需持续≥5天）
# ⚡ 立即确认 = 处于转变期/收敛末期/局部收敛时，当天突破即确认
broke_upper = close > upper

# 收敛 = 双线间距在 250 天中处于低百分位（<25分位）
# 局部收敛 = 通道宽度连续缩小 ≥4 天（不依赖历史百分位）
width_shrinking = channel_width[i] < channel_width[i-1]
local_converging = width_shrink_streak >= 4

# 收敛末期 = 连续收敛 ≥10 天
# 转变期 = 收敛末期之后 60 天内，突破确认之前
```

### 参数

- LOOKBACK_CONVERGENCE = 250（收敛/发散判定的历史窗口）
- CONVERGENCE_PERCENTILE = 25（宽度 < 此百分位 → 收敛态）
- DIVERGENCE_PERCENTILE = 75
- CONVERGENCE_MIN_DAYS = 10（连续收敛 ≥N 天 → 收敛末期）
- SUSTAIN_MIN_DAYS = 5（单边突破后需持续确认）
- TRANSITION_LOOKBACK = 60（转变期判定）
- LOCAL_CONVERGE_DAYS = 4（局部收敛窗口）

### 已知边界

- **V 型底无解**：急跌把通道间距炸开（如 2635 时 7.6%），反弹 13% 才追回通道。徐小明本人 2/6 承认"超跌反弹，不需要什么结构或序列"
- **缓跌底可提前**：2863 底时收敛提前 6 天预警
- **924 突破完美**：底部结构 + 局部收敛 + 当天突破 = 立即确认

### 与早期工具的关系

早期 `system_v2.py` 使用 `is_trend = abs(ma20_slope5) > 1% & price同侧MA20/MA60`。
该方法抓 MA20 速度（斜率），v5 加上了边界（通道突破）+ 收敛发散。斜率在 v5 中未复用，因为徐小明的通道方法更完整。
