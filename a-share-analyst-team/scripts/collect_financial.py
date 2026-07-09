#!/usr/bin/env python3
"""D6: 财务数据采集 → financial_data.json

调用财务摘要 + 财务指标。bs×2 串行，间隔 1~2s。
⚠️ 当前状态：a-share-finance-middleware 未完全就绪，部分函数可能返回空或 data_insufficient。
用法: python3 collect_financial.py --symbol 688386 --output /tmp/688386_20250622/data/financial_data.json
"""

import argparse, json, sys, time, random
from datetime import datetime

FUNCTIONS = []

# 尝试导入财务中间层函数
try:
    from a_share_finance_middleware.finance import (
        get_financial_abstract,
        get_financial_indicators,
    )
    FUNCTIONS = [
        ("financial_abstract",    get_financial_abstract),
        ("financial_indicators",  get_financial_indicators),
    ]
except ImportError:
    pass


def safe_call(func, name, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def main():
    parser = argparse.ArgumentParser(description="D6 财务采集")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if not FUNCTIONS:
        output = {
            "symbol": args.symbol,
            "collected_at": datetime.now().isoformat(),
            "data": {},
            "meta": {
                "note": "a-share-finance-middleware 未安装或未就绪，财务数据暂不可用",
                "functions_called": 0,
            },
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        print(f"financial_data.json → {args.output} (财务中间层未就绪，跳过)")
        return

    results = {}
    errors = []

    for idx, (key, func) in enumerate(FUNCTIONS):
        # bs 串行间隔
        if idx > 0:
            time.sleep(random.uniform(1.0, 2.0))
        result = safe_call(func, key, args.symbol)
        results[key] = result
        if not result.get("success", True):
            errors.append({key: result.get("error", "unknown")})

    output = {
        "symbol": args.symbol,
        "collected_at": datetime.now().isoformat(),
        "data": results,
        "errors": errors if errors else [],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    ok = len(FUNCTIONS) - len(errors)
    print(f"financial_data.json → {args.output} ({ok}/{len(FUNCTIONS)} OK)")


if __name__ == "__main__":
    main()
