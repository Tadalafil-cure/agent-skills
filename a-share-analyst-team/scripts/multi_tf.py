#!/usr/bin/env python3
"""
multi_tf.py — 多时间框架分析

输入：日线/周线/60min/30min K线 (dict of DataFrames)
      周线缺失时自动从日线 resample 生成（52-60 周）
输出：各周期趋势方向 + 共振/背离判断

用法：
  python multi_tf.py --input '<json>'     # {"daily": [...], "weekly": [...], "60min": [...], "30min": [...]}
  # 周线可选，无周线时从日线自动降频
"""

import json
import sys
import argparse
import numpy as np
import pandas as pd


def _parse_kline(data) -> pd.DataFrame:
    """解析 K 线 -> DataFrame（同 ta.py 逻辑）。"""
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, dict):
        arr = data.get("data", data.get("kline", []))
        df = pd.DataFrame(arr) if isinstance(arr, list) else pd.DataFrame(data)
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        return pd.DataFrame()

    col_map = {"day": "date", "trade_date": "date", "vol": "volume", "日期": "date", "时间": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    if df.empty or "close" not in df.columns:
        return df
    for c in ["open", "high", "low", "close"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return df


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def analyze_single(df: pd.DataFrame) -> dict:
    """单周期趋势分析。"""
    if df.empty or len(df) < 20:
        return {"trend": "数据不足", "close": None}

    close = df["close"]
    last = close.iloc[-1]

    # MA20 方向
    ma20 = close.rolling(20).mean()
    ma20_slope = (ma20.iloc[-1] / ma20.iloc[-6] - 1) if len(ma20) >= 6 and not pd.isna(ma20.iloc[-6]) else 0

    # MACD
    dif = ema(close, 12) - ema(close, 26)
    dea = ema(dif, 9)
    macd_direction = "上升" if dif.iloc[-1] > dif.iloc[-5] else "下降"
    dif_zero = "零轴上方" if dif.iloc[-1] > 0 else "零轴下方"

    # 趋势判断
    if ma20_slope > 0.005 and macd_direction == "上升":
        trend = "上升"
    elif ma20_slope < -0.005 and macd_direction == "下降":
        trend = "下降"
    else:
        trend = "震荡"

    return {
        "trend": trend,
        "close": round(last, 2),
        "ma20_slope_pct": round(ma20_slope * 100, 2),
        "macd_direction": macd_direction,
        "macd_zero": dif_zero,
        "data_points": len(df),
    }


def _resample_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """日线 → 周线降频：OHLC + 成交量求和。"""
    df = df_daily.copy()
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    w = df.resample("W")
    weekly = pd.DataFrame({
        "open": w["open"].first(),
        "high": w["high"].max(),
        "low": w["low"].min(),
        "close": w["close"].last(),
        "volume": w["volume"].sum(),
    }).dropna(subset=["close"]).reset_index()
    weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")
    # 保持降序（最新在前），与日线一致
    return weekly.sort_values("date", ascending=False).reset_index(drop=True)


def analyze_multi_timeframe(kline_dict: dict) -> dict:
    """多周期综合分析。"""
    # 如果未提供周线但有日线 → 从日线 resample
    if "weekly" not in kline_dict and "daily" in kline_dict:
        df_daily = _parse_kline(kline_dict["daily"])
        if not df_daily.empty and len(df_daily) >= 50:
            kline_dict = {**kline_dict, "weekly": _resample_weekly(df_daily)}

    results = {}
    for tf_name in ["weekly", "daily", "60min", "30min"]:
        if tf_name in kline_dict:
            df = _parse_kline(kline_dict[tf_name])
            results[tf_name] = analyze_single(df)
        else:
            results[tf_name] = {"trend": "数据缺失", "close": None}

    # 一致性判断
    trends = [v["trend"] for v in results.values() if v["trend"] not in ("数据不足", "数据缺失")]
    if not trends:
        return {**results, "alignment": "数据不足", "alignment_detail": "多周期数据均不足"}

    if all(t == "上升" for t in trends):
        alignment = "一致看多"
        detail = "所有周期方向一致向上，高确信做多"
    elif all(t == "下降" for t in trends):
        alignment = "一致看空"
        detail = "所有周期方向一致向下，高确信做空"
    elif any(t == "上升" for t in trends) and any(t == "下降" for t in trends):
        alignment = "周期冲突"
        detail = "长短期方向不一致——"
        if results.get("weekly", {}).get("trend") == "上升":
            detail += "周线看多(长周期主导)，短期回调可能是买入机会"
        elif results.get("weekly", {}).get("trend") == "下降":
            detail += "周线看空(长周期主导)，短期反弹可能是卖出机会"
    else:
        alignment = "部分震荡"
        detail = "部分周期方向不明确，建议观望"

    # 主导周期
    dominant = "周线" if results.get("weekly", {}).get("trend") not in ("数据不足", "数据缺失") else "日线"

    return {
        **results,
        "alignment": alignment,
        "alignment_detail": detail,
        "dominant_tf": dominant,
    }


def main():
    parser = argparse.ArgumentParser(description="多时间框架分析")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    args = parser.parse_args()

    data = json.loads(args.input) if args.input else json.load(sys.stdin)
    result = analyze_multi_timeframe(data)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
