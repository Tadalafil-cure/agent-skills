# 分钟线引擎 INDEX_MAP 硬编码陷阱

## 问题

`scripts/minute_structure_v2.py` 的 `INDEX_MAP` 虽然可以添加新指数，但 `main()` 函数的循环硬编码为 `for idx in ["sh", "sz"]:`——新增的 `cyb`、`kc` 等指数不会被执行。

## 表现

- 数据文件存在（`minute_raw_60/30_sh000688_科创50.csv` 已拉取）
- 引擎运行成功（无报错）
- 但 `minute_structure_v2_kc.csv` 和 `minute_structure_v2_cyb.csv` 不生成
- 报告中分钟线层标注「未覆盖」

## 根因

两处需要同时修改：

```python
# 位置1: 第23-26行 —— 添加新指数
INDEX_MAP = {
    "sh": ("sh000001", "上证指数"),
    "sz": ("sz399001", "深证成指"),
    "cyb": ("sz399006", "创业板指"),   # ← 新增
    "kc": ("sh000688", "科创50"),     # ← 新增
}

# 位置2: 第221行 —— 循环迭代 INDEX_MAP 而非硬编码
- for idx in ["sh", "sz"]:
+ for idx in INDEX_MAP:
```

只改位置1不改位置2 → 新指数静默跳过，无报错。

## 发现时间

2026-07-13 盘中全流程测试。此前科创50 分钟线分析一直标注「未覆盖」，本次测试中用户追问「科创50没有分钟线？」后排查发现。

## 影响范围

- `minute_structure_v2.py`：已修复（两处同步）
- `realtime.py` 的 `check_minute_structure()`：已受益于引擎修复，自动生成四指数文件
- SKILL.md 盘中流程描述：已更新为「四指数分钟线全覆盖」
