#!/usr/bin/env python3
"""D5: 资金流+筹码+龙虎榜采集 → stock_flow.json

调用: 主力资金 + 龙虎榜(1m/3m/6m) + 大宗交易(1m/6m) + 股东户数/十大/基金持仓 + 质押 + 融资融券。
源: em×4, bs×2。bs 必须串行且间隔 1~2s。
用法: python3 collect_flow.py --symbol 688386 --output /tmp/688386_20250622/data/stock_flow.json
"""

import argparse, json, sys, time, random
from datetime import datetime

from a_share_market_middleware.stock.flow import get_individual_fund_flow
from a_share_market_middleware.stock.lhb import get_lhb_stat
from a_share_market_middleware.stock.dzjy import get_dzjy_stat
from a_share_market_middleware.stock.holder import (
    get_shareholder_count, get_top10_shareholders, get_fund_holders,
)
from a_share_market_middleware.stock.gpzy import get_pledge_info
from a_share_market_middleware.stock.margin import get_margin_detail

# 调用列表: (key, func, args_tuple, is_bs)
FUNCTIONS = [
    ("fund_flow",           get_individual_fund_flow, (),                False),
    ("lhb_stat_1m",         get_lhb_stat,              ("近一月",),       False),
    ("lhb_stat_3m",         get_lhb_stat,              ("近三月",),       False),
    ("lhb_stat_6m",         get_lhb_stat,              ("近六月",),       False),
    ("dzjy_stat_1m",        get_dzjy_stat,             ("近一月",),       False),
    ("dzjy_stat_6m",        get_dzjy_stat,             ("近六月",),       False),
    ("shareholder_count",   get_shareholder_count,     (),                True),
    ("top10_shareholders",  get_top10_shareholders,    (),                True),
    ("fund_holders",        get_fund_holders,          (),                True),
    ("pledge_info",         get_pledge_info,           (),                False),
    ("margin_detail",       get_margin_detail,         (),                True),
]


def safe_call(func, name, sym, *args, **kwargs):
    try:
        return func(sym, *args, **kwargs)
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def bs_sleep():
    delay = random.uniform(1.0, 2.0)
    time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description="D5 资金流采集")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    results = {}
    errors = []

    for key, func, extra_args, is_bs in FUNCTIONS:
        if is_bs:
            bs_sleep()
        result = safe_call(func, key, args.symbol, *extra_args)
        results[key] = result
        if not result.get("success", True):
            errors.append({key: result.get("error", "unknown")})
        if not is_bs:
            time.sleep(0.5)

    output = {
        "symbol": args.symbol,
        "collected_at": datetime.now().isoformat(),
        "data": results,
        "errors": errors if errors else [],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    ok = len(FUNCTIONS) - len(errors)
    print(f"stock_flow.json → {args.output} ({ok}/{len(FUNCTIONS)} OK)")


if __name__ == "__main__":
    main()
