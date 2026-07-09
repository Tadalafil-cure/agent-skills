#!/usr/bin/env python3
"""D1: 市场全景数据采集 → market_data.json

调用 11 个中间层函数（legulegu 串行约束、无 em、无 bs）。
用法: python3 collect_market.py --symbol 688386 --output /tmp/688386_20250622/data/market_data.json
"""

import argparse, json, sys, time
from datetime import datetime

from a_share_market_middleware.overall.index_quotes import get_index_quotes
from a_share_market_middleware.overall.market import (
    get_market_breadth, get_market_activity, get_northbound_flow,
    get_margin_summary, get_ebs, get_buffett_index,
)
from a_share_market_middleware.sector.board import get_board_spot, get_board_fund_flow
from a_share_market_middleware.sector.concept import get_concept_spot

FUNCTIONS = [
    ("index_quotes",           get_index_quotes, (), {}),
    ("market_breadth",         get_market_breadth, (), {}),
    ("market_activity",        get_market_activity, (), {}),
    ("northbound_flow",        get_northbound_flow, (), {}),
    ("margin_summary",         get_margin_summary, (), {}),
    ("board_spot_industry",    get_board_spot, ("industry",), {}),
    ("concept_spot",           get_concept_spot, (), {}),
    ("board_fund_flow_industry", get_board_fund_flow, ("industry",), {}),
    ("board_fund_flow_concept",  get_board_fund_flow, ("concept",), {}),
    ("ebs",                    get_ebs, (), {}),
    ("buffett_index",          get_buffett_index, (), {}),
]


def safe_call(func, name, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def main():
    parser = argparse.ArgumentParser(description="D1 市场全景采集")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    results = {}
    errors = []

    for idx, (key, func, fargs, fkwargs) in enumerate(FUNCTIONS):
        result = safe_call(func, key, *fargs, **fkwargs)
        results[key] = result
        if not result.get("success", True):
            errors.append({key: result.get("error", "unknown")})
        # legulegu 串行间隔
        if idx < len(FUNCTIONS) - 1:
            time.sleep(0.5)

    output = {
        "success": len(errors) == 0,
        "data": results,
        "meta": {
            "collected_at": datetime.now().isoformat(),
            "stock_code": args.symbol,
            "functions_called": len(FUNCTIONS),
            "functions_succeeded": len(FUNCTIONS) - len(errors),
            "functions_failed": len(errors),
            "errors": errors if errors else None,
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"market_data.json → {args.output} ({len(FUNCTIONS)-len(errors)}/{len(FUNCTIONS)} OK)")


if __name__ == "__main__":
    main()
