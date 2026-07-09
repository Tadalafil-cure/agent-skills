#!/usr/bin/env python3
"""
prepare_inputs.py — Step 0.3: 将 collection 产出拆分为各消费脚本所需格式

问题：stock_kline.json 的嵌套结构与 ta/volume_price/volume_classifier/
      risk_quant/multi_tf 各脚本的 --input 格式均不兼容，每次 Agent 需手工
       reshape 5~10 步。

解法：Step 0 完成后跑一次本脚本，输出到 data/inputs/，各脚本直接 --file。

用法：
  python prepare_inputs.py --kline data/stock_kline.json --outdir data/inputs/
"""

import argparse, json, os, sys
from pathlib import Path


def _strip_meta(obj: dict) -> dict:
    """剥离 middleware 元数据，保留 data + source。"""
    return {k: v for k, v in obj.items() if k not in ("success", "meta", "degraded_from", "sources_tried", "error")}


def _data_array(obj: dict) -> list:
    """从 middleware 输出提取 raw data 数组。"""
    if isinstance(obj, list):
        return obj
    return obj.get("data", [])


def prepare(inputs: dict) -> dict[str, str]:
    """
    inputs = {
        "kline": "/path/to/stock_kline.json",   # Step 0 collect_kline 产出
    }
    返回 {script_key: json_str}。
    """
    with open(inputs["kline"]) as f:
        kline = json.load(f)
    data = kline.get("data", kline)

    dk = data.get("daily_kline", {})
    mk60 = data.get("minute_kline_60", {})
    mk30 = data.get("minute_kline_30", {})
    quote = data.get("realtime_quote", {})

    results = {}

    # ── ta.py ──
    # _parse_kline 取 data.get("data") → 直接传 middleware 输出即可
    results["ta"] = json.dumps(dk, ensure_ascii=False, default=str)

    # ── volume_price.py ──
    # data.get("stock", data).get("kline_daily", {})
    results["vp"] = json.dumps({"stock": {"kline_daily": dk}}, ensure_ascii=False, default=str)

    # ── volume_classifier.py ──
    # data.get("stock", data).get("quote", {}).get("data", quote)
    results["vc"] = json.dumps({"stock": {"quote": quote}}, ensure_ascii=False, default=str)

    # ── risk_quant.py ──
    # data.get("symbol_kline", data.get("kline", []))
    # 传 raw data 数组
    results["risk"] = json.dumps({"symbol_kline": _data_array(dk)}, ensure_ascii=False, default=str)

    # ── multi_tf.py ──
    # analyze_multi_timeframe 取 dict 的 weekly/daily/60min/30min 键
    tf = {}
    tf["daily"] = _data_array(dk)
    tf["60min"] = _data_array(mk60) if mk60 else []
    tf["30min"] = _data_array(mk30) if mk30 else []
    results["mtf"] = json.dumps(tf, ensure_ascii=False, default=str)

    return results


def main():
    parser = argparse.ArgumentParser(description="统一脚本输入格式转换")
    parser.add_argument("--kline", required=True, help="stock_kline.json 路径")
    parser.add_argument("--outdir", required=True, help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    results = prepare({"kline": args.kline})

    written = []
    for key, content in results.items():
        path = os.path.join(args.outdir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(f"{key}.json")

    print(f"✓ {len(written)} 输入文件 → {args.outdir}/ ({', '.join(written)})")


if __name__ == "__main__":
    main()
