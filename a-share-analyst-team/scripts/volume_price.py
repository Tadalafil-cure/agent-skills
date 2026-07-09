#!/usr/bin/env python3
"""
volume_price.py — 量价配合四宫格引擎

输入：data_package.stock.kline_daily (日K线)
输出：量价配合四宫格矩阵结果

判定规则：
  放量 = 当日成交量 > MA(VOL, 20) × 1.5
  缩量 = 当日成交量 < MA(VOL, 20) × 0.7
  平量 = 0.7~1.5
  上涨 = 当日收盘 > 昨收
  下跌 = 当日收盘 < 昨收

用法：
  python volume_price.py --file /tmp/agent_c1_data.json
  python volume_price.py --input '<json>'
  cat data.json | python volume_price.py
"""

import json
import sys
import argparse

import numpy as np
import pandas as pd


def _parse_kline(data) -> pd.DataFrame:
    """解析日K线为DataFrame（同 ta.py 的 _parse_kline 逻辑）。"""
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, dict):
        arr = data.get("data", data.get("kline", []))
        if isinstance(arr, list):
            df = pd.DataFrame(arr)
        else:
            raise ValueError(f"无法解析 K 线数据: {type(data)}")
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        raise ValueError(f"无法解析 K 线数据: {type(data)}")

    col_map = {
        "day": "date", "trade_date": "date",
        "open": "open", "high": "high", "low": "low", "close": "close",
        "volume": "volume", "vol": "volume",
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "amount",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Handle nested formats: {"data": [...], ...} or raw list
    if isinstance(df, dict):
        if "data" in df and isinstance(df["data"], list):
            df = pd.DataFrame(df["data"])
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        elif any(isinstance(v, list) for v in df.values()):
            for v in df.values():
                if isinstance(v, list) and len(v) > 0:
                    df = pd.DataFrame(v)
                    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                    break

    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "close" not in df.columns:
        raise KeyError(f"volume_price: missing required column 'close'. Available: {list(df.columns)[:20]}")
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)
    return df


def classify(df: pd.DataFrame) -> dict:
    """量价配合四宫格判定。"""
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return {"error": "缺少成交量数据"}

    close = df["close"]
    vol = df["volume"]

    # MA(VOL, 20)
    vol_ma = vol.rolling(window=20).mean()
    last_vol = vol.iloc[-1]
    last_vol_ma = vol_ma.dropna().iloc[-1] if len(vol_ma.dropna()) > 0 else last_vol

    if last_vol_ma == 0:
        ratio = 1.0
    else:
        ratio = last_vol / last_vol_ma

    # 量能分档
    if ratio > 1.5:
        vol_label = "放量"
    elif ratio < 0.7:
        vol_label = "缩量"
    else:
        vol_label = "平量"

    # 涨跌判定
    if len(close) >= 2:
        price_change = (close.iloc[-1] / close.iloc[-2] - 1) * 100
    else:
        price_change = 0

    if price_change > 0:
        price_label = "上涨"
    elif price_change < 0:
        price_label = "下跌"
    else:
        price_label = "平盘"

    # 四宫格映射
    matrix = {
        ("放量", "上涨"): {"signal": "✅ 健康", "desc": "多头动能强，趋势延续"},
        ("缩量", "上涨"): {"signal": "⚠️ 背离", "desc": "动能减弱，警惕诱多"},
        ("平量", "上涨"): {"signal": "→ 正常", "desc": "温和上涨，趋势正常"},
        ("放量", "下跌"): {"signal": "❌ 恶化", "desc": "抛压沉重，空头主导"},
        ("缩量", "下跌"): {"signal": "🔄 衰竭", "desc": "惜售明显，接近底部"},
        ("平量", "下跌"): {"signal": "→ 偏弱", "desc": "常态下跌，无恐慌"},
        ("放量", "平盘"): {"signal": "⚡ 分歧", "desc": "多空激烈博弈"},
        ("缩量", "平盘"): {"signal": "→ 观望", "desc": "交投清淡，等待方向"},
        ("平量", "平盘"): {"signal": "→ 正常", "desc": "正常盘整"},
    }

    verdict = matrix.get((vol_label, price_label), {"signal": "未知", "desc": ""})

    return {
        "latest_volume": int(last_vol),
        "vol_ma20": int(last_vol_ma),
        "ratio": round(ratio, 2),
        "vol_label": vol_label,
        "price_change_pct": round(price_change, 2),
        "price_label": price_label,
        "signal": verdict["signal"],
        "description": verdict["desc"],
    }


def main():
    parser = argparse.ArgumentParser(description="量价配合四宫格引擎")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    parser.add_argument("--file", type=str, help="JSON 文件路径")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
    elif args.input:
        data = json.loads(args.input)
    else:
        data = json.load(sys.stdin)

    stock = data.get("stock", data)
    kline = stock.get("kline_daily", {})

    # Handle collect_kline.py output format: {"data": {"daily_kline": {"data": [...]}}}
    if not kline or (isinstance(kline, dict) and not isinstance(kline, list)):
        if "data" in data and isinstance(data["data"], dict):
            d2 = data["data"]
            if "daily_kline" in d2:
                kline = d2["daily_kline"]
                if isinstance(kline, dict) and "data" in kline:
                    kline = kline["data"]

    df = _parse_kline(kline)
    result = classify(df)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
