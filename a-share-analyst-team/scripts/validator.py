#!/usr/bin/env python3
"""
validator.py — 历史信号胜率验证

输入：日K线 + 信号类型 + 回溯窗口
输出：历史胜率/平均收益/最大回撤/信号衰减

用法：
  python validator.py --input '<json>'     # {"kline": [...], "signal_type": "MACD金叉", "lookback": 500}
"""

import json
import sys
import argparse
import numpy as np
import pandas as pd


def _parse_kline(data) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, dict):
        arr = data.get("data", data.get("kline", []))
        df = pd.DataFrame(arr) if isinstance(arr, list) else pd.DataFrame(data)
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        return pd.DataFrame()
    col_map = {"day": "date", "trade_date": "date", "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    for c in ["close"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return df


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def detect_macd_cross(df: pd.DataFrame) -> list:
    """检测 MACD 金叉/死叉。"""
    close = df["close"]
    dif = ema(close, 12) - ema(close, 26)
    dea = ema(dif, 9)
    signals = []
    for i in range(1, len(dif)):
        if dif.iloc[i-1] <= dea.iloc[i-1] and dif.iloc[i] > dea.iloc[i]:
            signals.append({"index": i, "type": "MACD金叉", "date": str(df["date"].iloc[i])})
        elif dif.iloc[i-1] >= dea.iloc[i-1] and dif.iloc[i] < dea.iloc[i]:
            signals.append({"index": i, "type": "MACD死叉", "date": str(df["date"].iloc[i])})
    return signals


def validate_signal(kline_df, signal_type="MACD金叉", lookback=500) -> dict:
    """验证信号历史表现。"""
    if kline_df.empty or len(kline_df) < 60:
        return {"error": "K线数据不足（需 ≥60 日）"}

    df = kline_df.iloc[-lookback:] if len(kline_df) > lookback else kline_df
    close = df["close"]

    # 检测信号
    signals = detect_macd_cross(df)
    if signal_type == "MACD金叉":
        signals = [s for s in signals if s["type"] == "MACD金叉"]
    elif signal_type == "MACD死叉":
        signals = [s for s in signals if s["type"] == "MACD死叉"]

    if len(signals) < 3:
        return {
            "signal": signal_type,
            "historical_occurrences": len(signals),
            "warning": "历史信号不足（<3次），统计不可靠",
        }

    # 计算每次信号发生后 N 日的收益
    results_5d = []
    results_10d = []
    results_20d = []
    max_drawdowns_20d = []

    for s in signals:
        idx = s["index"]
        entry_price = close.iloc[idx]

        # 5日
        if idx + 5 < len(close):
            ret_5d = (close.iloc[idx + 5] / entry_price - 1) * 100
            results_5d.append(ret_5d)

        # 10日
        if idx + 10 < len(close):
            ret_10d = (close.iloc[idx + 10] / entry_price - 1) * 100
            results_10d.append(ret_10d)

        # 20日
        if idx + 20 < len(close):
            ret_20d = (close.iloc[idx + 20] / entry_price - 1) * 100
            results_20d.append(ret_20d)
            # 最大回撤
            window = close.iloc[idx:idx+20]
            cummax = window.expanding().max()
            dd = ((window - cummax) / cummax).min() * 100
            max_drawdowns_20d.append(dd)

    def _stats(arr):
        if not arr:
            return None
        return {
            "win_rate": round(sum(1 for x in arr if x > 0) / len(arr), 2),
            "avg_return": round(np.mean(arr), 2),
            "median_return": round(np.median(arr), 2),
            "occurrences": len(arr),
        }

    result = {
        "signal": signal_type,
        "historical_occurrences": len(signals),
        "lookback_days": len(df),
    }

    if results_5d:
        result["win_rate_5d"] = round(sum(1 for x in results_5d if x > 0) / len(results_5d), 2)
        result["avg_return_5d"] = round(np.mean(results_5d), 2)
    if results_10d:
        result["win_rate_10d"] = round(sum(1 for x in results_10d if x > 0) / len(results_10d), 2)
        result["avg_return_10d"] = round(np.mean(results_10d), 2)
    if results_20d:
        result["win_rate_20d"] = round(sum(1 for x in results_20d if x > 0) / len(results_20d), 2)
        result["avg_return_20d"] = round(np.mean(results_20d), 2)
        result["max_drawdown_20d"] = round(min(max_drawdowns_20d), 2) if max_drawdowns_20d else None

    # ⛔ 不做信号衰减和置信度裁决 —— Agent E 根据 win_rate 自主判断
    return result


def main():
    parser = argparse.ArgumentParser(description="历史信号胜率验证")
    parser.add_argument("--input", type=str, help="JSON 字符串 (含 kline + signal_type + lookback)")
    args = parser.parse_args()

    data = json.loads(args.input) if args.input else json.load(sys.stdin)
    kline = _parse_kline(data.get("kline", data.get("kline_daily", [])))
    signal_type = data.get("signal_type", "MACD金叉")
    lookback = int(data.get("lookback", 500))
    result = validate_signal(kline, signal_type, lookback)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
