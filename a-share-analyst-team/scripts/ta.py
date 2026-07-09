#!/usr/bin/env python3
"""
ta.py — 技术指标计算引擎

继承：geek-a-share-analyst + cn-stock-analyst 指标规则表
输入：日K线 OHLCV (DataFrame 或 JSON) + 实时行情
输出：结构化 JSON (均线/MACD/RSI/KDJ/布林/ATR/成交量/K线形态)

用法：
  python ta.py --input '<json>'     # JSON 字符串
  python ta.py --file <path>        # JSON 文件
"""

import json
import sys
import argparse
import math
from typing import Optional

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════

def _parse_kline(data) -> pd.DataFrame:
    """从多种格式解析 K 线为 DataFrame（columns: date, open, high, low, close, volume）。"""
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

    # 统一列名
    col_map = {
        "day": "date", "trade_date": "date",
        "open": "open", "high": "high", "low": "low", "close": "close",
        "volume": "volume", "vol": "volume",
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "amount",
        "振幅": "amplitude", "涨跌幅": "change_pct", "涨跌额": "change_amount", "换手率": "turnover",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    required = ["date", "open", "high", "low", "close"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"K 线数据缺少必需列: {c}")
        if c == "date":
            continue  # 日期列不转数值（保留字符串，供 sort_values 使用）
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    df = df.dropna(subset=["close"]).reset_index(drop=True)
    # 按日期升序（ta 计算需要时间顺序）
    df = df.sort_values("date").reset_index(drop=True)
    return df


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均。"""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均。"""
    return series.rolling(window=period).mean()


# ═══════════════════════════════════════════════
# 指标计算
# ═══════════════════════════════════════════════

def compute_ma(df: pd.DataFrame) -> dict:
    """均线系统：MA5/10/20/60/120 + 排列判断。"""
    close = df["close"]
    result = {}
    for p in [5, 10, 20, 60, 120]:
        if len(close) >= p:
            ma = sma(close, p)
            result[f"MA{p}"] = [round(x, 2) if not pd.isna(x) else None for x in ma.tolist()]

    # 排列判断（基于最后一日）
    if len(close) >= 5:
        last = {}
        for k, v in result.items():
            vals = [x for x in v if x is not None]
            if vals:
                last[k] = vals[-1]

        if all(k in last for k in ["MA5", "MA10", "MA20"]):
            if last["MA5"] > last["MA10"] > last["MA20"]:
                result["arrangement"] = "多头排列"
            elif last["MA5"] < last["MA10"] < last["MA20"]:
                result["arrangement"] = "空头排列"
            else:
                result["arrangement"] = "交叉缠绕"

    return result


def compute_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> dict:
    """MACD：DIF/DEA/柱状图 + 金叉死叉 + 背离检测。"""
    close = df["close"]
    dif = ema(close, fast) - ema(close, slow)
    dea = ema(dif, signal)
    hist = 2 * (dif - dea)

    result = {
        "DIF": [round(x, 4) if not pd.isna(x) else None for x in dif.tolist()],
        "DEA": [round(x, 4) if not pd.isna(x) else None for x in dea.tolist()],
        "hist": [round(x, 4) if not pd.isna(x) else None for x in hist.tolist()],
    }

    # 金叉/死叉检测
    cross_up = []
    cross_down = []
    for i in range(1, len(dif)):
        if dif.iloc[i-1] <= dea.iloc[i-1] and dif.iloc[i] > dea.iloc[i]:
            cross_up.append({"index": int(i), "date": str(df["date"].iloc[i])})
        elif dif.iloc[i-1] >= dea.iloc[i-1] and dif.iloc[i] < dea.iloc[i]:
            cross_down.append({"index": int(i), "date": str(df["date"].iloc[i])})

    if cross_up and (not cross_down or cross_up[-1]["index"] > cross_down[-1]["index"]):
        result["signal"] = "金叉买入"
    elif cross_down and (not cross_up or cross_down[-1]["index"] > cross_up[-1]["index"]):
        result["signal"] = "死叉卖出"
    else:
        result["signal"] = "无交叉"

    # 背离检测：遍历所有相邻显著峰/谷对
    n_hist = min(250, len(close))
    if n_hist >= 60:
        # 在全量数据中找显著极值点（prominence > 3%）
        recent_c = close.iloc[-n_hist:].values
        recent_d = dif.iloc[-n_hist:].values
        
        def _find_significant_peaks(arr, order=10):
            pk = []
            for i in range(order, len(arr) - order):
                window = arr[i-order:i+order+1]
                if arr[i] != max(window):
                    continue
                left_base = min(arr[i-order:i])
                right_base = min(arr[i+1:i+order+1])
                prominence = (arr[i] - max(left_base, right_base)) / abs(arr[i]) if arr[i] != 0 else 0
                if prominence > 0.03:
                    pk.append(i)
            return pk
        
        def _find_significant_troughs(arr, order=10):
            tr = []
            for i in range(order, len(arr) - order):
                window = arr[i-order:i+order+1]
                if arr[i] != min(window):
                    continue
                left_base = max(arr[i-order:i])
                right_base = max(arr[i+1:i+order+1])
                prominence = (min(left_base, right_base) - arr[i]) / abs(arr[i]) if arr[i] != 0 else 0
                if prominence > 0.03:
                    tr.append(i)
            return tr
        
        # 顶背离：遍历相邻峰对 — 价格↑ + DIF↓
        price_peaks = _find_significant_peaks(recent_c, order=10)
        for i in range(len(price_peaks) - 1):
            p1, p2 = price_peaks[i], price_peaks[i+1]
            if recent_c[p2] > recent_c[p1] * 1.01:
                if recent_d[p2] < recent_d[p1] * 0.95:
                    result["divergence"] = "顶背离"
                    break
        
        # 底背离：遍历相邻谷对 — 价格↓ + DIF↑
        if "divergence" not in result:
            price_troughs = _find_significant_troughs(recent_c, order=10)
            for i in range(len(price_troughs) - 1):
                t1, t2 = price_troughs[i], price_troughs[i+1]
                if recent_c[t2] < recent_c[t1] * 0.99:
                    if recent_d[t2] > recent_d[t1] * 1.05:
                        result["divergence"] = "底背离"
                        break
        
        if "divergence" not in result:
            result["divergence"] = "无背离"

    return result


def compute_rsi(df: pd.DataFrame, period=14) -> dict:
    """RSI 相对强弱指标。"""
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))

    values = [round(x, 2) if not pd.isna(x) else None for x in rsi.tolist()]
    last_val = next((x for x in reversed(values) if x is not None), None)

    zone = "正常"
    if last_val is not None:
        if last_val >= 80:
            zone = "严重超买"
        elif last_val >= 70:
            zone = "超买"
        elif last_val <= 20:
            zone = "严重超卖"
        elif last_val <= 30:
            zone = "超卖"

    return {"value": last_val, "zone": zone, "values": values}


def compute_kdj(df: pd.DataFrame, n=9, m1=3, m2=3) -> dict:
    """KDJ 随机指标。"""
    close = df["close"]
    high_n = df["high"].rolling(window=n).max()
    low_n = df["low"].rolling(window=n).min()
    rsv = ((close - low_n) / (high_n - low_n).replace(0, 1e-10)) * 100

    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    j = 3 * k - 2 * d

    k_vals = [round(x, 2) if not pd.isna(x) else None for x in k.tolist()]
    d_vals = [round(x, 2) if not pd.isna(x) else None for x in d.tolist()]
    j_vals = [round(x, 2) if not pd.isna(x) else None for x in j.tolist()]

    result = {"K": k_vals, "D": d_vals, "J": j_vals}

    # 金叉/死叉
    last_k = next((x for x in reversed(k_vals) if x is not None), None)
    last_d = next((x for x in reversed(d_vals) if x is not None), None)
    last_j = next((x for x in reversed(j_vals) if x is not None), None)

    if last_k is not None and last_d is not None:
        if last_k > last_d:
            result["signal"] = "K在D上方"
            if last_j is not None and last_j >= 100:
                result["signal"] = "高位死叉风险"
        else:
            result["signal"] = "K在D下方"
            if last_j is not None and last_j <= 0:
                result["signal"] = "低位金叉机会"

    if last_j is not None:
        if last_j > 100:
            result["J_signal"] = "超买"
        elif last_j < 0:
            result["J_signal"] = "超卖"

    return result


def compute_bollinger(df: pd.DataFrame, period=20, std=2) -> dict:
    """布林带。"""
    close = df["close"]
    mid = sma(close, period)
    std_dev = close.rolling(window=period).std(ddof=0)  # 布林带用总体标准差
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    bandwidth = (upper - lower) / mid.replace(0, 1e-10)

    result = {
        "upper": [round(x, 2) if not pd.isna(x) else None for x in upper.tolist()],
        "mid": [round(x, 2) if not pd.isna(x) else None for x in mid.tolist()],
        "lower": [round(x, 2) if not pd.isna(x) else None for x in lower.tolist()],
    }

    # 位置判断
    last_close = close.iloc[-1]
    last_upper = upper.iloc[-1]
    last_mid = mid.iloc[-1]
    last_lower = lower.iloc[-1]
    last_bw = bandwidth.iloc[-1]

    if not pd.isna(last_close) and not pd.isna(last_upper):
        if last_close >= last_upper:
            result["position"] = "突破上轨"
        elif last_close <= last_lower:
            result["position"] = "跌破下轨"
        elif last_close > last_mid:
            result["position"] = "中轨上方"
        else:
            result["position"] = "中轨下方"

    if not pd.isna(last_bw):
        bw_series = bandwidth.dropna()
        if len(bw_series) >= 20:
            bw_pct = (bw_series.iloc[-1] - bw_series.iloc[-20:].min()) / (bw_series.iloc[-20:].max() - bw_series.iloc[-20:].min() + 1e-10)
            if bw_pct < 0.2:
                result["bandwidth"] = "极度收窄"
            elif bw_pct < 0.4:
                result["bandwidth"] = "收窄"
            elif bw_pct > 0.8:
                result["bandwidth"] = "宽幅"
            else:
                result["bandwidth"] = "正常"

    return result


def compute_atr(df: pd.DataFrame, period=14) -> dict:
    """ATR 平均真实波幅。"""
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()

    last_atr = atr.dropna().iloc[-1] if len(atr.dropna()) > 0 else None
    last_close = close.iloc[-1]
    pct = round(last_atr / last_close * 100, 2) if last_atr and last_close else None

    return {"value": round(last_atr, 2) if last_atr else None, "pct": pct}


def compute_adx(df: pd.DataFrame, period=14) -> dict:
    """ADX/DMI 趋势强度指标。"""
    high, low, close = df["high"], df["low"], df["close"]

    # True Range
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()

    # +DM / -DM
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # Smoothed
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, 1e-10))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, 1e-10))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    last_vals = {}
    for name, series in [("ADX", adx), ("+DI", plus_di), ("-DI", minus_di)]:
        v = series.dropna()
        last_vals[name] = round(v.iloc[-1], 2) if len(v) > 0 else None

    # 趋势强度判定
    adx_val = last_vals.get("ADX")
    if adx_val is None:
        strength = "数据不足"
    elif adx_val >= 40:
        strength = "极强趋势"
    elif adx_val >= 25:
        strength = "趋势市"
    elif adx_val >= 20:
        strength = "弱趋势"
    else:
        strength = "无趋势/震荡"

    return {
        "ADX": last_vals.get("ADX"),
        "+DI": last_vals.get("+DI"),
        "-DI": last_vals.get("-DI"),
        "strength": strength,
    }


def compute_volume(df: pd.DataFrame, period=20) -> dict:
    """成交量分析：量比 + 量价配合。"""
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return {"ratio": None, "trend": "无成交量数据"}

    vol = df["volume"]
    vol_ma = sma(vol, period)
    last_vol = vol.iloc[-1]
    last_vol_ma = vol_ma.dropna().iloc[-1] if len(vol_ma.dropna()) > 0 else 1
    ratio = round(last_vol / last_vol_ma, 2) if last_vol_ma else None

    # 量价配合：今日涨跌 vs 今日量能（相对 MA20）
    close = df["close"]
    price_change_today = close.pct_change(1)  # 今日 vs 昨日
    last_pc = price_change_today.iloc[-1]
    
    trend = "正常"
    if ratio is not None and not pd.isna(last_pc):
        if last_pc > 0.01 and ratio > 1.5:
            trend = "放量上涨"
        elif last_pc > 0.01 and ratio < 0.5:
            trend = "缩量上涨(量价背离)"
        elif last_pc < -0.01 and ratio > 1.5:
            trend = "放量下跌"
        elif last_pc < -0.01 and ratio < 0.5:
            trend = "缩量下跌"

    return {"ratio": ratio, "trend": trend, "vol_ma": round(last_vol_ma, 0) if last_vol_ma else None}


def compute_candlestick(df: pd.DataFrame, lookback=20) -> list:
    """K 线形态识别（最近 N 根）。"""
    open_, high, low, close = df["open"], df["high"], df["low"], df["close"]
    patterns = []
    n = min(lookback, len(df) - 1)

    for i in range(len(df) - n, len(df)):
        o, h, l, c = open_.iloc[i], high.iloc[i], low.iloc[i], close.iloc[i]
        body = abs(c - o)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        total_range = h - l
        if total_range == 0:
            continue

        body_ratio = body / total_range
        date = str(df["date"].iloc[i])

        # 锤子线 / 倒锤子
        if body_ratio < 0.3:
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                patterns.append({"date": date, "pattern": "锤子线", "direction": "bullish"})
            elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
                patterns.append({"date": date, "pattern": "倒锤子", "direction": "bearish"})

        # 十字星
        if body_ratio < 0.1:
            patterns.append({"date": date, "pattern": "十字星", "direction": "neutral"})

        # 吞没形态
        if i > 0:
            prev_o, prev_c = open_.iloc[i-1], close.iloc[i-1]
            prev_body = abs(prev_c - prev_o)
            if c > o and prev_c < prev_o and o <= prev_c and c >= prev_o:
                patterns.append({"date": date, "pattern": "看涨吞没", "direction": "bullish"})
            elif c < o and prev_c > prev_o and o >= prev_c and c <= prev_o:
                patterns.append({"date": date, "pattern": "看跌吞没", "direction": "bearish"})

    return patterns


# ═══════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════

def compute_all(df: pd.DataFrame, quote: Optional[dict] = None) -> dict:
    """计算全部技术指标，返回结构化 JSON。"""
    result = {
        "ma": compute_ma(df),
        "macd": compute_macd(df),
        "rsi": compute_rsi(df),
        "kdj": compute_kdj(df),
        "boll": compute_bollinger(df),
        "atr": compute_atr(df),
        "adx": compute_adx(df),
        "volume": compute_volume(df),
        "candlestick": compute_candlestick(df),
    }

    # 价格摘要
    close = df["close"]
    result["price"] = {
        "latest": round(close.iloc[-1], 2),
        "change_pct_5d": round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6 else None,
        "change_pct_20d": round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else None,
        "high_20d": round(df["high"].iloc[-20:].max(), 2) if len(df) >= 20 else None,
        "low_20d": round(df["low"].iloc[-20:].min(), 2) if len(df) >= 20 else None,
    }

    if quote:
        result["realtime"] = quote

    return result


def main():
    parser = argparse.ArgumentParser(description="技术指标计算引擎")
    parser.add_argument("--input", type=str, help="JSON 字符串 (K线数据)")
    parser.add_argument("--file", type=str, help="JSON 文件路径")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
    elif args.input:
        data = json.loads(args.input)
    else:
        # 尝试从 stdin 读取
        data = json.load(sys.stdin)

    df = _parse_kline(data)
    quote = data.get("quote") if isinstance(data, dict) else None
    result = compute_all(df, quote)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
