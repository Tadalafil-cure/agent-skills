# 规则引擎上下文窗口修复（2026-07-11）

## 问题

规则引擎 `rule_engine.py` 在裁决阶段只读单行数据：
```python
u = unimp[unimp["date"]==date]  # 只取 1 行！
trend_cross = int(u["trend_cross"].iloc[0])  # 0 或 1
```

而各独立引擎（structure_engine 等）跑时有 40-250 天 lookback 上下文，汇总时全部丢失。

## 后果

- 250 天 trend_cross=1 中，118 天（47%）发生在震荡·无信号市况
- 其中 107 天是纯趋势交叉（无结构/钝化配合）
- 引擎精确率仅 35%

## 修复

裁决阶段（run_pipeline 阶段3）加载 250 日上下文窗口：

```python
window_start = date - pd.Timedelta(days=400)  # ~250个交易日
win_unimp = unimp[(unimp["date"] >= window_start) & (unimp["date"] <= window_end)]
win_mc = mc[...]
win_daily = daily[...]
```

三层过滤：
1. 震荡市 + 纯趋势交叉（无结构/钝化）→ 降级为噪音
2. 10天内≥3次趋势交叉 → 反复穿越 → 降级
3. 年度震荡占比>60% → 信号置信度低 → 降级

## 验证

| 场景 | 测试 | 结果 |
|------|------|------|
| 震荡·无信号 + 纯趋势交叉 | 10天 | 10/10 过滤 ✓ |
| 单边趋势 + 趋势交叉 | 5天 | 5/5 保留 ✓ |
| 震荡 + 结构形成 | 5天 | 5/5 保留 ✓ |

## 多周期趋势一致性（2026-07-11）

### 问题

`weekly_ma_channels.csv` 和 `monthly_ma_channels.csv` 在 data 目录中存在（Phase 1 fetch_data 已采集），但 `rule_engine.py` 从未加载。徐小明原文中高频出现多周期框架——"周线趋势完好+日线有结构→级别大"——引擎完全没有这个维度。

### 修复

`rule_engine.py` 已加载周线/月线数据（`__main__` 块 + `run_pipeline` 阶段3e2）：

```python
weekly  = pd.read_csv("weekly_ma_channels.csv")
monthly = pd.read_csv("monthly_ma_channels.csv")
```

多周期趋势一致性检测：
- 日线上升但周线下降 → 逆大势信号，级别有限
- 日/周/月三周期共振上升/下降 → 信号可信度高
- 日周冲突 → 日线信号降权（不改变重要/不重要判断，但降置信度）

简报输出新增多周期行：
```
多周期: 日/周/月共振 ↑
多周期: ⚠️ 日周冲突
```

### 关键教训

数据采集（Phase 1）和引擎集成（Phase 2/3）之间存在断裂。fetch_data.py 采集了周线月线，但 rule_engine.py 忘了接。后续新增数据源时须同步更新规则引擎加载代码。

## 盲测方法论演进

v1-v9 迭代的关键教训：
- 以交易日为锚（非文章），随机抽 → 引擎出结果 → 找当天文章比对
- 只用收盘后操作策略文章，剔除午评（文章太短，信息不足）
- 比对维度：操作动作 > 趋势方向 > 信号检测 > "不重要"判断
- 正则提取徐小明声明不可靠 → 应直接展示原文关键句供人工比对
