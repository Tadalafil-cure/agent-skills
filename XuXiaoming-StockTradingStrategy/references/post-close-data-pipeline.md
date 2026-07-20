# 收盘后数据管线延迟处理

## 问题

收盘后（15:00）立即运行 `build.py` 或 `fetch.py --mode daily` 时，akshare 的日线 OHLC 端点最新数据仅到前一交易日。例如 7/13 15:05 运行 fetch，输出日期截止 7/10。

这不是 akshare 的 bug，是数据源（新浪/东方财富）的日线数据通常在收盘后 30-60 分钟才更新。收盘后立即跑全流程会拿到残缺数据。

## 解决方案：两步走

### Step 1：用盘中 spot 数据补全 daily_raw

```python
from data_layer.realtime import get_spot
import pandas as pd

spot = get_spot()  # Sina 实时行情，收盘后可获取最终收盘价

code_map = {
    '上证指数': 'sh000001', '深证成指': 'sz399001',
    '创业板指': 'sz399006', '科创50': 'sh000688',
    '沪深300': 'sh000300', '中证500': 'sh000905'
}

daily = pd.read_csv('data/daily_raw.csv')
new_rows = []
for name, code in code_map.items():
    if name in spot:
        s = spot[name]
        new_rows.append({
            'date': 'YYYY-MM-DD', 'index_code': code, 'index_name': name,
            'open': s['open'], 'high': s['high'], 'low': s['low'],
            'close': s['price'], 'volume': s.get('volume', 0)
        })

daily = daily[daily['date'] != 'YYYY-MM-DD']  # 去重
daily = pd.concat([daily, pd.DataFrame(new_rows)], ignore_index=True)
daily = daily[['date','index_code','index_name','open','high','low','close','volume']]
daily.to_csv('data/daily_raw.csv', index=False)
```

### Step 2：重跑管线

```bash
python data_layer/process.py    # 重新处理 → structure_signals + turn_sequence_events + verdict_v7
python scripts/verdict_v7.py    # 确保当日数据进入判决
python scripts/minute_structure_v2.py  # 分钟线结构
```

## 列名陷阱

`daily_raw.csv` 的列名是 `index_code` / `index_name`，不是 `code` / `name`。`get_spot()` 返回的 key 是中文指数名，需映射到 `index_code`。写错列名→verdict 引擎读不到→当天判决缺失。

## 分钟线数据

分钟线通过 `check_minute_structure()` 自动拉取，收盘后重跑 `minute_structure_v2.py` 即可得到完整当日分钟线结构。

## 后备数据源：东方财富实时 API

当 Sina API（`hq.sinajs.cn`）不可用时，东方财富 `push2.eastmoney.com` 的实时行情是可靠后备：

```bash
# 六指数收盘价 + 涨跌幅
curl -s --max-time 10 \
  "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001,0.399006,1.000688,1.000300,1.000905&fields=f2,f3,f4,f12,f14"
```

字段映射：`f2`=现价，`f3`=涨跌幅%，`f4`=涨跌额，`f12`=代码，`f14`=名称。

注意：此 API 返回的是**盘中实时价**（收盘后=收盘价），不含 OHLC 全字段。如需全字段补全 daily_raw，优先用 Sina spot 数据；如需快速获取收盘快照（仅价格+涨跌幅），直接用此 API。
