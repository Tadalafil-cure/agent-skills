#!/usr/bin/env python3
"""D3: 估值与规模对比采集 → stock_valuation.json

调用行业估值对比 + 规模排名 + 公司概况。em×2 内串行。
用法: python3 collect_valuation.py --symbol 688386 --output /tmp/688386_20250622/data/stock_valuation.json
"""

import argparse, json, sys
from datetime import datetime

from a_share_market_middleware.stock.comparison import (
    get_industry_valuation_comparison,
    get_scale_comparison,
)
from a_share_market_middleware.stock.profile import get_company_profile


FUNCTIONS = [
    ("industry_valuation_comparison", get_industry_valuation_comparison),
    ("scale_comparison",              get_scale_comparison),
    ("company_profile",               get_company_profile),
]


def safe_call(func, name, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def main():
    parser = argparse.ArgumentParser(description="D3 估值+规模采集")
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

    print(f"stock_valuation.json → {args.output} ({len(FUNCTIONS)-len(errors)}/{len(FUNCTIONS)} OK)")


if __name__ == "__main__":
    main()
