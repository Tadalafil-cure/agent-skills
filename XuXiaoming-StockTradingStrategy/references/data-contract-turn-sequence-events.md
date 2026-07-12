# turn_sequence_events.csv 数据合约

> 此文件由 `data_layer/process.py` 生成，被 `scripts/verdict_v7.py` 消费。
> **修改此合约任一侧，必须同步更新另一侧。**

## 列定义

| 列名 | 类型 | 值域 | 说明 |
|------|------|------|------|
| `index_name` | str | 上证指数/深证成指/创业板指/沪深300/中证500 | 指数名称 |
| `date` | str | YYYY-MM-DD | 信号日期 |
| `period` | str | `日线` / `周线` / `月线` | 序列周期。⚠️ 带"线"字！ |
| `seq_type` | str | `高9` / `低9` | 序列类型+值。⚠️ 完整值，非 direction+拼接！ |
| `seq_value` | int | 8-10 | 序列计数值 |

## 消费者检查清单

修改 `process.py` 的序列生成逻辑后，必须验证 `verdict_v7.py` 中的以下引用：

- `load_seq()` → `row['period']` 存储为 key → `verdict_single()` 中 `seq_data.get(d, {}).get('日线')` 
- `load_seq()` → `row['seq_type']` 直接存储 → 比对 `'高9'` / `'低9'`
- 月周窗口查找 → `'月线' in seq_data[cd]` / `'周线' in seq_data[cd]`

## 已知坑 (2026-07-12 修复)

- `period` 值用 "日线"/"周线"/"月线"，不是 "日"/"周"/"月"
- `seq_type` 值用 "高9"/"低9"，不是 `direction + '9'`
- 这两个不一致曾导致 `verdict_v7.py` 静默跳过所有序列信号
