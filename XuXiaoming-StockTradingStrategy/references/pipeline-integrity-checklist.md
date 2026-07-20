# 管线完整性校验清单

> 每次 `build.py` 完成后强制执行四层验证。未通过任何一层 → 不出报告。

---

## 第一层：日线覆盖

```bash
python3 -c "
import pandas as pd
from datetime import datetime
d = pd.read_csv('data/daily_raw.csv', parse_dates=['date'])
today = datetime.now().strftime('%Y-%m-%d')
latest = d['date'].max().strftime('%Y-%m-%d')
print(f'日线: {d[\"date\"].min().date()} ~ {latest}')
print(f'预期: 应覆盖到 {today}')
print(f'状态: {\"✅\" if latest >= today else \"❌ 滞后\"}  ')
"
```

**通过标准**：六指数最新日期 ≥ 今日。若滞后 >0 天 → fetch.py 时效检测未生效或 Sina 接口不可用。

---

## 第二层：分钟线覆盖

```bash
for f in data/minute_raw_60_*.csv; do
  echo "$f: $(grep -c $(date +%Y-%m-%d) $f) 根今日K线"
done
```

**通过标准**：六指数各 4 根 60min K 线（收盘后）。交易日盘中可能 <4 根。

---

## 第三层：文件数量

```bash
ls data/minute_structure_v2_*.csv | wc -l  # 应为 4
ls data/daily_raw.csv data/structure_signals.csv \
   data/turn_sequence_events.csv data/verdict_v7.csv | wc -l  # 应为 4
```

**通过标准**：分钟线结构 4 文件（sh/sz/cyb/kc）+ 核心输出 4 文件。

---

## 第四层：代码-文档一致性

```bash
# fetch.py docstring vs 代码逻辑
grep -c "时效检测\|today > latest" data_layer/fetch.py  # 应 >0

# process.py outputs list
grep -c "minute_structure_v2_cyb\|minute_structure_v2_kc" data_layer/process.py  # 应 >=2

# SKILL.md 数据源描述
grep "akshare 优先 + 时效检测" SKILL.md | wc -l  # 应 >=2
```

**通过标准**：四层全部 green → 管线可信，可安全出报告。
