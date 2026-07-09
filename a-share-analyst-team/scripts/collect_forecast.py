#!/usr/bin/env python3
"""D4: 盈利预测与研报采集 → stock_forecast.json

调用 EPS预测 + 预测综合指标 + 研报覆盖。em×3 内串行。
用法: python3 collect_forecast.py --symbol 688386 --output /tmp/688386_20250622/data/stock_forecast.json
"""

import argparse, json, sys
from datetime import datetime

from a_share_market_middleware.stock.forecast import (
    get_profit_forecast_eps,
    get_profit_forecast_metrics,
)
from a_share_market_middleware.stock.research import get_research_reports


FUNCTIONS = [
    ("profit_forecast_eps",     get_profit_forecast_eps),
    ("profit_forecast_metrics", get_profit_forecast_metrics),
    ("research_reports",        get_research_reports),
]


def safe_call(func, name, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def main():
    parser = argparse.ArgumentParser(description="D4 预测+研报采集")
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

    print(f"stock_forecast.json → {args.output} ({len(FUNCTIONS)-len(errors)}/{len(FUNCTIONS)} OK)")


if __name__ == "__main__":
    main()
