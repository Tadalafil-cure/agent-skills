# ddgs 多轮搜索测试方法

> 用于验证 ddgs 搜索工具的限频和拆分策略是否生效。
> 关联：硬约束 #21（a-share-analyst-team）、deep-search v1.2、duckduckgo-search Pitfalls。

## 测试脚本模板

```python
import time, sys
sys.path.insert(0, "scripts")
import collect_web_search as cs  # 或目标模块

_orig = cs.search_ddgs
timestamps = []

def timed_search(query, max_results=10):
    ts = time.time()
    result = _orig(query, max_results)
    elapsed = time.time() - ts
    timestamps.append((ts, query, elapsed, len(result)))
    return result

cs.search_ddgs = timed_search

tests = [
    "京泉华 002885",
    "京泉华 产能 订单 项目",
    "京泉华 技术 客户 产品",
]

for q in tests:
    timed_search(q)

gaps = [timestamps[i][0] - timestamps[i-1][0] for i in range(1, len(timestamps))]
for i, g in enumerate(gaps, 1):
    status = "OK" if g >= 20 else "FAIL"
    print(f"R{i}->R{i+1}: {g:.1f}s {status}")
```

## 验收标准

| 指标 | 阈值 | 说明 |
|------|------|------|
| 每轮结果数 | >0 | 零结果 = 限频或长词截断 |
| 轮间间隔 | ≥32s（12s sleep + ~20s 搜索） | 文件锁强制 ≥20s |
| 文件锁触发 | 预期至少触发一次 | `[ddgs] 距上次搜索 X.Xs, 等待 Y.Ys...` |
| 全轮次 | 6/6 全过（3 个股 + 3 行业） | 零超时 |

## 已知失败模式

- **单轮长查询 → 0 结果**：`"京泉华 002885 业务 技术 产能"` 经 Google 后端截断返空。必拆短词。
- **轮间无 sleep → R2 超时**：连续搜索 <20s 间隔触发 Google 限频。必须显式 sleep ≥12s。
- **行业长查询必挂**：旧版 `"{行业} 产业链 景气度 上下游 订单 出货量"` 7 词。必拆三轮。

## 实测记录（2026-06-27 京泉华 002885）

```
R1 个股·综合: 10条, 21.9s
  → 冷却 12s
R2 个股·产能: 10条, 20.0s
  → 冷却 12s → 文件锁: 距上次 18.3s, 等待 1.7s
R3 个股·技术: 10条, 15.0s
  → 文件锁: 距上次 4.5s, 等待 15.5s
R4 行业·产业链: 10条
  → 冷却 12s
R5 行业·供需: 10条
  → 冷却 12s
R6 行业·政策: 10条

6/6 全过, 零超时。个股 30→23(去重)→10条。行业 30→20→10条。
```
