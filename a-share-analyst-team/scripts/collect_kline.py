#!/usr/bin/env python3
"""D2: 个股K线数据采集 → stock_kline.json

调用日K线 + 60min/30min分钟K线 + 实时行情。
源: tx×2, sina×2。内串行无并发冲突。
用法: python3 collect_kline.py --symbol 688386 --output /tmp/688386_20250622/data/stock_kline.json
"""

import argparse, json, sys

from datetime import datetime, timedelta

from a_share_market_middleware.stock.kline import get_daily_kline, get_minute_kline
from a_share_market_middleware.stock.realtime import get_realtime_quote

# 日线拉 500 天（~350 交易日 → ~70 周），保证 multi_tf.py 周线 resample 有 60 周足够数据
_END_DATE = datetime.now().strftime("%Y%m%d")
_START_DATE = (datetime.now() - timedelta(days=500)).strftime("%Y%m%d")

FUNCTIONS = [
    ("daily_kline",      lambda sym: get_daily_kline(sym, start_date=_START_DATE, end_date=_END_DATE)),
    ("minute_kline_60",  lambda sym: get_minute_kline(sym, period=60)),
    ("minute_kline_30",  lambda sym: get_minute_kline(sym, period=30)),
    ("realtime_quote",   lambda sym: get_realtime_quote(sym)),
]


def safe_call(func, name, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def main():
    parser = argparse.ArgumentParser(description="D2 K线采集")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    results = {}
    errors = []

    for key, func in FUNCTIONS:
        result = safe_call(func, key, args.symbol)
        results[key] = result
        if not result.get("success", True):
            errors.append({key: result.get("error", "unknown")})

    output = {
        "symbol": args.symbol,
        "success": len(errors) == 0,
        "data": results,
        "meta": {
            "collected_at": datetime.now().isoformat(),
            "functions_called": len(FUNCTIONS),
            "functions_succeeded": len(FUNCTIONS) - len(errors),
            "functions_failed": len(errors),
            "errors": errors if errors else None,
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"stock_kline.json → {args.output} ({len(FUNCTIONS)-len(errors)}/{len(FUNCTIONS)} OK)")


if __name__ == "__main__":
    main()
