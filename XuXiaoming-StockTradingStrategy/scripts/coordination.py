#!/usr/bin/env python3
"""
指数协调性检测器 H7

徐小明原文（2019-2026多处提及）：
  "指数之间的协调性并不好，结构的级别不大"（2020）
  "三大指数情况各异，协调性不好"（2020）
  "多指数共振"是增强信号的核心条件

核心思想：
  六大指数方向一致 → 信号可信度高
  指数分化/部分走强部分走弱 → 信号降权

四维度协调性：
  ① 趋势方向一致度：MA20>MA60 的指数数量（上升趋势共识）
  ② 价格位置一致度：价格>MA20 的指数数量（短期趋势共识）
  ③ 通道收敛一致度：通道收敛的指数数量（转折共识）
  ④ 综合协调分：以上三项的加权平均
"""

import pandas as pd, numpy as np, os, sys

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
INDICES = ["sh000001","sz399001","sz399006","sh000688","sh000300","sh000905"]


def compute_coordination(daily_path: str) -> pd.DataFrame:
    daily = pd.read_csv(daily_path)
    daily["date"] = pd.to_datetime(daily["date"])
    dates = sorted(daily["date"].unique())
    n_idx = len(INDICES)
    n_days = len(dates)

    # 每日每个维度的共识数
    trend_agree = np.zeros(n_days, dtype=int)     # MA20>MA60
    price_agree = np.zeros(n_days, dtype=int)     # 价格>MA20
    converge_agree = np.zeros(n_days, dtype=int)  # 通道收敛

    for code in INDICES:
        df = daily[daily["index_code"]==code].sort_values("date")
        m = pd.DataFrame({"date": dates}).merge(
            df[["date","ma20_above_ma60","above_ma20","channel_converging"]],
            on="date", how="left"
        )
        trend_agree += m["ma20_above_ma60"].fillna(0).values.astype(int)
        price_agree += m["above_ma20"].fillna(0).values.astype(int)
        converge_agree += m["channel_converging"].fillna(0).values.astype(int)

    # 协调分（0-100）：三维度平均 * 100/6
    coord_score = ((trend_agree + price_agree + converge_agree) / 3 / n_idx * 100).astype(float)

    # 定性等级
    def classify(s):
        if s >= 83: return "高度一致"    # ≥5/6 共识
        elif s >= 67: return "基本一致"   # ≥4/6
        elif s >= 50: return "部分分化"   # ≥3/6
        elif s >= 33: return "明显分化"   # ≥2/6
        else: return "严重分化"           # ≤1/6

    levels = np.array([classify(s) for s in coord_score])

    result = pd.DataFrame({
        "date": dates,
        "trend_agree": trend_agree,       # MA20>MA60的指数数
        "price_agree": price_agree,       # 价格>MA20的指数数
        "converge_agree": converge_agree, # 通道收敛的指数数
        "coord_score": np.round(coord_score, 1),
        "coord_level": levels,
    })

    return result


def report(result: pd.DataFrame):
    total = len(result)
    print("=" * 70)
    print("指数协调性检测器 H7")
    print("=" * 70)

    print(f"\n  总交易日: {total}")
    print(f"\n  协调等级分布:")
    for lvl in ["高度一致","基本一致","部分分化","明显分化","严重分化"]:
        n = (result["coord_level"]==lvl).sum()
        bar = "█" * (n * 40 // total)
        print(f"    {lvl:<8} {n:>5}d ({n/total*100:>5.1f}%) {bar}")

    print(f"\n  趋势->价格->收敛 三维度均值:")
    print(f"    趋势一致(MA20>MA60): {result['trend_agree'].mean():.1f}/6")
    print(f"    价格一致(>MA20):     {result['price_agree'].mean():.1f}/6")
    print(f"    收敛一致:            {result['converge_agree'].mean():.1f}/6")

    # 年度
    result["year"] = pd.to_datetime(result["date"]).dt.year
    print(f"\n  年度协调分均值:")
    for yr in sorted(result["year"].unique()):
        y = result[result["year"]==yr]
        avg = y["coord_score"].mean()
        consistent = (y["coord_level"].isin(["高度一致","基本一致"])).sum()
        bar = "█" * int(avg / 5) + "░" * (20 - int(avg / 5))
        print(f"    {yr}: {avg:>5.1f}分  高/基一致{consistent:>4}d/{len(y)} "
              f"({consistent/len(y)*100:.0f}%) {bar}")

    # 高度分化的时段
    divided = result[result["coord_level"].isin(["明显分化","严重分化"])].copy()
    if len(divided) > 0:
        # 找连续分化段
        divided["d"] = pd.to_datetime(divided["date"])
        streaks = []
        s = 0
        for i in range(1, len(divided)):
            if (divided["d"].iloc[i] - divided["d"].iloc[i-1]).days <= 3:
                s += 1
            else:
                if s >= 5:
                    streaks.append((divided["d"].iloc[i-s-1], divided["d"].iloc[i-1], s+1))
                s = 0

        if streaks:
            print(f"\n  明显/严重分化连续段（≥5天）:")
            for start, end, days in sorted(streaks, key=lambda x: -x[2])[:8]:
                print(f"    {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}  {days}d")

    # 高度一致的时段
    consistent = result[result["coord_level"]=="高度一致"].copy()
    print(f"\n  高度一致段统计:")
    print(f"    总天数: {len(consistent)} ({len(consistent)/total*100:.1f}%)")
    if len(consistent) > 0:
        consistent["d"] = pd.to_datetime(consistent["date"])
        # 分上升/下跌
        mc_path = os.path.join(DATA, "market_condition_xu_v2.csv")
        if os.path.exists(mc_path):
            mc = pd.read_csv(mc_path)
            mc["date"] = pd.to_datetime(mc["date"])
            merged = consistent.merge(mc[["date","condition"]], on="date", how="left")
            for c in ["单边上升","单边下跌","震荡·有信号","震荡·无信号"]:
                n = (merged["condition"]==c).sum()
                if n > 0:
                    pct = n / len(merged) * 100
                    print(f"      其中 {c}: {n}d ({pct:.0f}%)")


if __name__ == "__main__":
    daily_path = os.path.join(DATA, "daily_ma_channels.csv")
    if not os.path.exists(daily_path):
        print("请先运行 scripts/fetch_data.py")
        sys.exit(1)
    result = compute_coordination(daily_path)
    report(result)
    out = os.path.join(DATA, "index_coordination.csv")
    result.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n→ {out}")
