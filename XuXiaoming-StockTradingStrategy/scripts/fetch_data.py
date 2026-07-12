#!/usr/bin/env python3
"""
操作层 · 基础数据提取 + MA20/MA60 趋势通道
只做数据提取和基础计算，不做信号判断。
信号判断由上层规则引擎负责。

指数：上证/深成指/创业板/上证50/沪深300/中证500
周期：日线
来源：akshare stock_zh_index_daily (东方财富)
"""

import akshare as ak
import pandas as pd
import numpy as np
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = str(BASE_DIR / "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

INDICES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
}


def fetch_daily(index_code: str, name: str, start: str = "20190101") -> pd.DataFrame | None:
    """拉单个指数日线 OHLCV"""
    try:
        df = ak.stock_zh_index_daily(symbol=index_code)
        df = df.rename(columns={
            "date": "date", "open": "open", "high": "high",
            "low": "low", "close": "close", "volume": "volume"
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["date"] >= start].sort_values("date").reset_index(drop=True)
        df["index_name"] = name
        df["index_code"] = index_code
        print(f"  {name}: {len(df)} 条 ({df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')})")
        return df
    except Exception as e:
        print(f"  {name}: 失败 — {e}")
        return None


def calc_ma_channels(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 MA20/MA60 趋势通道。
    
    徐小明核心用法：
    - 短期趋势 = MA20，长期趋势 = MA60
    - 收盘价 > MA20 且 MA20 > MA60 → 上升趋势，趋势之上
    - 收盘价 < MA60 且 MA60 > MA20 → 下降趋势，趋势之下
    - 价格夹在 MA20 和 MA60 之间 → 趋势纠缠/震荡
    
    通道收敛 = MA20 和 MA60 的间距在缩小
    通道发散 = 间距在扩大
    """
    df["ma20"] = df["close"].rolling(20, min_periods=20).mean()
    df["ma60"] = df["close"].rolling(60, min_periods=60).mean()

    # 通道间距
    df["channel_width"] = abs(df["ma20"] - df["ma60"])
    df["channel_width_pct"] = df["channel_width"] / df["close"] * 100

    # 价格与通道的关系
    df["above_ma20"] = (df["close"] > df["ma20"]).astype(int)
    df["above_ma60"] = (df["close"] > df["ma60"]).astype(int)
    df["ma20_above_ma60"] = (df["ma20"] > df["ma60"]).astype(int)

    # 趋势状态
    conditions = [
        (df["close"] > df["ma20"]) & (df["ma20"] > df["ma60"]),
        (df["close"] < df["ma20"]) & (df["ma20"] < df["ma60"]),
    ]
    df["trend_state"] = np.select(conditions, [2, 0], default=1)

    # 距 MA20/MA60 的距离（用于判断"距趋势近/远"）
    df["dist_to_ma20"] = df["close"] - df["ma20"]
    df["dist_to_ma60"] = df["close"] - df["ma60"]
    df["dist_to_ma20_pct"] = df["dist_to_ma20"] / df["close"] * 100
    df["dist_to_ma60_pct"] = df["dist_to_ma60"] / df["close"] * 100

    # 通道收敛/发散（20日窗口内 width 的变化方向）
    df["channel_width_20d_ago"] = df["channel_width"].shift(20)
    df["channel_converging"] = (df["channel_width"] < df["channel_width_20d_ago"]).astype(int)

    return df


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """日线 → 周线，周五收盘价"""
    df = df.set_index("date")
    w = df.resample("W-FRI", closed="right", label="right").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    w = w.reset_index()
    return calc_ma_channels(w)


def resample_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """日线 → 月线"""
    df = df.set_index("date")
    m = df.resample("ME", closed="right", label="right").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    m = m.reset_index()
    return calc_ma_channels(m)


def main():
    print("=" * 50)
    print("XuXiaoming-StockTradingStrategy · 基础数据")
    print(f"输出: {OUTPUT_DIR}")
    print("=" * 50)

    # 拉数据
    print("\n[1] 拉日线...")
    dfs = []
    for code, name in INDICES.items():
        df = fetch_daily(code, name)
        if df is not None:
            dfs.append(df)

    if not dfs:
        print("❌ 无数据")
        return

    # 计算通道
    print("\n[2] 计算 MA20/MA60 通道...")
    processed = []
    for df in dfs:
        df = calc_ma_channels(df)
        name = df["index_name"].iloc[0]
        code = df["index_code"].iloc[0]

        # 统计
        states = df["trend_state"].value_counts()
        up = states.get(2, 0)
        mid = states.get(1, 0)
        down = states.get(0, 0)
        total = len(df)
        print(f"  {name}: 上升{up}({up/total*100:.0f}%) 纠缠{mid}({mid/total*100:.0f}%) 下降{down}({down/total*100:.0f}%)")

        processed.append(df)

    # 保存
    print("\n[3] 保存日线...")
    all_data = pd.concat(processed, ignore_index=True)
    path = os.path.join(OUTPUT_DIR, "daily_ma_channels.csv")
    all_data.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  → {path} ({len(all_data)} 行)")

    # --- 周线 ---
    print("\n[4] 重采样周线...")
    weekly_dfs = []
    for df in dfs:
        name = df["index_name"].iloc[0]
        code = df["index_code"].iloc[0]
        w = resample_weekly(df)
        w["index_name"] = name
        w["index_code"] = code
        weekly_dfs.append(w)
        print(f"  {name}: {len(w)} 周K线")
    all_weekly = pd.concat(weekly_dfs, ignore_index=True)
    path_w = os.path.join(OUTPUT_DIR, "weekly_ma_channels.csv")
    all_weekly.to_csv(path_w, index=False, encoding="utf-8-sig")
    print(f"  → {path_w} ({len(all_weekly)} 行)")

    # --- 月线 ---
    print("\n[5] 重采样月线...")
    monthly_dfs = []
    for df in dfs:
        name = df["index_name"].iloc[0]
        code = df["index_code"].iloc[0]
        m = resample_monthly(df)
        m["index_name"] = name
        m["index_code"] = code
        monthly_dfs.append(m)
        print(f"  {name}: {len(m)} 月K线")
    all_monthly = pd.concat(monthly_dfs, ignore_index=True)
    path_m = os.path.join(OUTPUT_DIR, "monthly_ma_channels.csv")
    all_monthly.to_csv(path_m, index=False, encoding="utf-8-sig")
    print(f"  → {path_m} ({len(all_monthly)} 行)")

    date_range = f"{all_data['date'].min().strftime('%Y-%m-%d')} ~ {all_data['date'].max().strftime('%Y-%m-%d')}"
    print(f"\n  日期范围: {date_range}")
    print("=" * 50)


if __name__ == "__main__":
    main()
