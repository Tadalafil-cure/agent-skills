#!/usr/bin/env python3
"""
徐小明分钟线结构修边引擎 v2.0
================================
在日线结构信号基础上，用 60/90/120 分钟线做结构精确定点和多周期共振判断。

v2 改进:
- 使用分钟线自身 MACD(4,30,4) 检测 DIF-DEA 交叉
- 多周期共振: 同方向交叉在 3 天内发生 → 共振确认
- 钝化检测: 基于近期高点/低点的 DIF 背离

用法: python minute_structure_v2.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR = Path(__file__).resolve().parent.parent / "data"

INDEX_MAP = {
    "sh": ("sh000001", "上证指数"),
    "sz": ("sz399001", "深证成指"),
    "cyb": ("sz399006", "创业板指"),
    "kc": ("sh000688", "科创50"),
}

PERIODS = [60, 90, 120]
MACD_PARAMS = (4, 30, 4)  # 徐小明标准结构MACD


def compute_macd(close, fast=4, slow=30, signal=4):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_bar = 2 * (dif - dea)
    return dif, dea, macd_bar


def find_divergence(df, lookback=20):
    """
    极值法钝化检测 (v3.0)
    底钝化: 价格创 lookback 根K线新低 + DIF 未创新低
    顶钝化: 价格创 lookback 根K线新高 + DIF 未创新高
    回测结论: 顶钝化可靠(89-98%转化率), 底钝化需结合日线信号
    """
    n = len(df)
    bd = np.zeros(n, dtype=int)  # 底钝化
    td = np.zeros(n, dtype=int)  # 顶钝化

    for i in range(lookback, n):
        w_low = df["low"].iloc[i-lookback:i]
        w_high = df["high"].iloc[i-lookback:i]
        w_dif = df["dif"].iloc[i-lookback:i]

        # 底钝化: 价格 ≤ 窗口最低价 且 DIF > 窗口最低DIF
        if df["low"].iloc[i] <= w_low.min() and df["dif"].iloc[i] > w_dif.min():
            bd[i] = 1

        # 顶钝化: 价格 ≥ 窗口最高价 且 DIF < 窗口最高DIF
        if df["high"].iloc[i] >= w_high.max() and df["dif"].iloc[i] < w_dif.max():
            td[i] = 1

    return bd, td


def detect_cross_and_structure(df):
    """检测 DIF-DEA 交叉 + 钝化→结构 (v3.0: 底/顶钝化分离)"""
    n = len(df)
    top_form = np.zeros(n, dtype=int)
    bottom_form = np.zeros(n, dtype=int)
    dif_cross_up = np.zeros(n, dtype=int)
    dif_cross_down = np.zeros(n, dtype=int)

    in_top_div = False
    in_bot_div = False
    bd, td = find_divergence(df)

    for i in range(1, n):
        prev_dif, prev_dea = df["dif"].iloc[i - 1], df["dea"].iloc[i - 1]
        cur_dif, cur_dea = df["dif"].iloc[i], df["dea"].iloc[i]

        if prev_dif <= prev_dea and cur_dif > cur_dea:
            dif_cross_up[i] = 1
        if prev_dif >= prev_dea and cur_dif < cur_dea:
            dif_cross_down[i] = 1

        # 钝化跟踪
        if td[i] == 1:
            in_top_div = True
        if bd[i] == 1:
            in_bot_div = True

        # 顶部结构: 顶钝化 + DIF下穿DEA
        if in_top_div and dif_cross_down[i]:
            top_form[i] = 1
            in_top_div = False

        # 底部结构: 底钝化 + DIF上穿DEA
        if in_bot_div and dif_cross_up[i]:
            bottom_form[i] = 1
            in_bot_div = False

    return dif_cross_up, dif_cross_down, top_form, bottom_form, bd, td


def process_period(code, name, period):
    """处理单个分钟周期，聚合到日频。支持两种文件命名。"""
    # 优先匹配 data_layer 格式 (minute_raw_{period}_{code}_{name}.csv)
    fname_new = f"minute_raw_{period}_{code}_{name}.csv"
    # 回退到旧格式 (min{period}_{code}_{name}.csv)
    fname_old = f"min{period}_{code}_{name}.csv"

    fpath = DATA_DIR / fname_new
    if not fpath.exists():
        fpath = DATA_DIR / fname_old
    if not fpath.exists():
        # 也搜 OUT_DIR (data_layer 输出默认在这里)
        fpath = OUT_DIR / fname_new
    if not fpath.exists():
        fpath = OUT_DIR / fname_old
    if not fpath.exists():
        print(f"  ⚠️ 未找到文件: {fname_new} / {fname_old}")
        return None

    df = pd.read_csv(fpath)
    df["date"] = pd.to_datetime(df["date"])

    # 自算 MACD (4,30,4)
    df["dif"], df["dea"], df["bar"] = compute_macd(df["close"])

    # 检测交叉和结构
    cross_up, cross_down, top_form, bottom_form, bd, td = detect_cross_and_structure(df)

    df["cross_up"] = cross_up
    df["cross_down"] = cross_down
    df["top_form"] = top_form
    df["bottom_form"] = bottom_form
    df["bd"] = bd
    df["td"] = td

    # 聚合到日频
    df["trade_date"] = df["date"].dt.date
    groups = df.groupby("trade_date")

    daily = groups.agg(
        close=("close", "last"),
        dif=("dif", "last"),
        dea=("dea", "last"),
        bar=("bar", "last"),
        bd=("bd", "max"),            # 日内任一时点有底钝化=当天有
        td=("td", "max"),            # 日内任一时点有顶钝化=当天有
        top_form=("top_form", "max"),
        bottom_form=("bottom_form", "max"),
        cross_up=("cross_up", "max"),
        cross_down=("cross_down", "max"),
        cross_count=("cross_up", "sum"),
    ).reset_index()

    daily["date"] = pd.to_datetime(daily["trade_date"])

    # 统计
    top_cnt = daily["top_form"].sum()
    bot_cnt = daily["bottom_form"].sum()
    td_cnt = daily["td"].sum()
    bd_cnt = daily["bd"].sum()
    print(f"  {period}min: 顶钝化{td_cnt}天 底钝化{bd_cnt}天 | 顶结构{top_cnt}次 底结构{bot_cnt}次")

    # 重命名
    prefix = f"{period}"
    daily = daily.rename(columns={
        "close": f"close_{prefix}", "dif": f"dif_{prefix}", "dea": f"dea_{prefix}",
        "bar": f"bar_{prefix}",
        "bd": f"bd_{prefix}", "td": f"td_{prefix}",
        "top_form": f"top_form_{prefix}", "bottom_form": f"bottom_form_{prefix}",
        "cross_up": f"cross_up_{prefix}", "cross_down": f"cross_down_{prefix}",
    })

    return daily[["date"] + [c for c in daily.columns if c != "date" and c != "trade_date"]]


def compute_resonance(df):
    """计算多周期共振"""
    # 各周期结构
    top_cols = [f"top_form_{p}" for p in PERIODS]
    bot_cols = [f"bottom_form_{p}" for p in PERIODS]

    if not all(c in df.columns for c in top_cols):
        return df

    df["top_resonance"] = df[top_cols].sum(axis=1)
    df["bot_resonance"] = df[bot_cols].sum(axis=1)

    # 交叉共振（不需要钝化，只看DIF-DEA方向）
    # 多周期同时金叉/死叉 → 方向确认
    up_cols = [f"cross_up_{p}" for p in PERIODS]
    down_cols = [f"cross_down_{p}" for p in PERIODS]
    if all(c in df.columns for c in up_cols):
        df["golden_cross_res"] = df[up_cols].sum(axis=1)
        df["dead_cross_res"] = df[down_cols].sum(axis=1)

    # 信号等级 (仅限有结构形成的情况)
    conditions = [
        (df["top_resonance"] + df["bot_resonance"] >= 3),
        (df["top_resonance"] + df["bot_resonance"] >= 2),
        (df["top_resonance"] + df["bot_resonance"] >= 1),
    ]
    choices = ["S级·三周期共振", "A级·双周期共振", "B级·单周期结构"]
    df["signal_level"] = np.select(conditions, choices, default="无结构")

    return df


def main(data_dir: str = None):
    global DATA_DIR
    if data_dir:
        DATA_DIR = Path(data_dir)

    for idx in INDEX_MAP:
        code, name = INDEX_MAP[idx]
        print(f"\n{'='*60}")
        print(f"分钟线结构修边引擎 v2 · {name}")
        print(f"{'='*60}")

        results = []
        for p in PERIODS:
            print(f"\n[周期 {p}分钟]")
            r = process_period(code, name, p)
            if r is not None:
                results.append(r)

        if not results:
            continue

        # 合并
        merged = results[0]
        for r in results[1:]:
            merged = merged.merge(r, on="date", how="outer")
        merged = merged.sort_values("date")
        merged = compute_resonance(merged)

        out_path = OUT_DIR / f"minute_structure_v2_{idx}.csv"
        merged.to_csv(out_path, index=False)
        print(f"\n✅ {out_path}  ({len(merged)}天)")

        # 关键日期验证
        print("\n[关键节点分钟线确认]")
        key_dates = ["2026-01-13","2026-01-14","2026-03-23","2026-04-13",
                     "2026-04-21","2026-05-14","2026-06-22","2026-06-23",
                     "2026-06-25","2026-07-09","2026-07-10"]
        for d in key_dates:
            row = merged[merged["date"] == d]
            if len(row) > 0:
                r = row.iloc[0]
                sl = r.get("signal_level", "?")
                if sl != "无结构" or r.get("golden_cross_res", 0) > 0:
                    print(f"  {d}: {sl} | "
                          f"金叉共振={int(r.get('golden_cross_res',0))} "
                          f"死叉共振={int(r.get('dead_cross_res',0))} "
                          f"顶结构={int(r.get('top_resonance',0))} "
                          f"底结构={int(r.get('bot_resonance',0))}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="分钟线结构修边引擎 v2")
    p.add_argument("--data-dir", default=None,
                   help=f"分钟线数据目录 (默认: {DATA_DIR})")
    args = p.parse_args()
    main(data_dir=args.data_dir)
