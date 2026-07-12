#!/usr/bin/env python3
"""
"不重要"检测器

基于徐小明原文定义（2026-06-04）：

  "不重要 = 不改变操作结果。操作结果由两件事决定：
   ① 趋势是否被跌穿/突破
   ② 钝化是否消失/结构是否形成
   过程是怎样波动的，波动幅度大小都不能导致结果产生，
   这些过程就都不重要。"

操作结果改变事件（六指数任一触发即算）:
  - 趋势突破: 收盘上穿 MA20 且 MA20>MA60
  - 趋势破位: 收盘下穿 MA60 且 MA20<MA60
  - 结构形成: 顶部/底部结构形成
  - 钝化消失: 钝化消失（纠错信号）

方法定位:
  这是徐小明"化繁为简"的核心工具之一。它不输出"该做什么"，
  而是输出"今天是否需要在操作上做决策"。
  其反向结果——"今天不重要"——帮助用户过滤掉市场中61%的噪音。

输出:
  - data/unimportant_daily.csv（每日六指数操作改变标记 + 全市场汇总）
"""

import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from structure_engine import process_structure

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
INDICES = ["sh000001","sz399001","sz399006","sh000688","sh000300","sh000905"]
NAMES = {"sh000001":"上证","sz399001":"深证","sz399006":"创业板",
         "sh000688":"科创50","sh000300":"沪深300","sh000905":"中证500"}


def detect_unimportant(daily_path: str, mc_path: str = None):
    """
    检测每日是否"不重要"（不改变操作结果）。

    返回 DataFrame:
      date, trend_cross, struct_form, div_lost,
      result_change (1=重要/改变结果, 0=不重要),
      n_changing (当天几个指数触发改变),
      condition (市况标签，如有 mc_path)
    """
    daily = pd.read_csv(daily_path)
    daily["date"] = pd.to_datetime(daily["date"])
    dates = sorted(daily["date"].unique())
    n_days = len(dates)
    date_to_idx = {d: i for i, d in enumerate(dates)}

    # 操作结果改变事件
    trend_cross = np.zeros(n_days, dtype=int)
    struct_form = np.zeros(n_days, dtype=int)
    div_lost    = np.zeros(n_days, dtype=int)
    n_changing  = np.zeros(n_days, dtype=int)  # 当天几个指数触发

    for code in INDICES:
        df = daily[daily["index_code"]==code].sort_values("date").reset_index(drop=True)
        if df.empty or len(df) < 60:
            continue
        df = process_structure(df)

        for i in range(1, len(df)):
            d = df["date"].iloc[i]
            if d not in date_to_idx:
                continue
            idx = date_to_idx[d]
            changed = False

            # ① 趋势突破/破位
            c = df["close"].iloc[i]; m20 = df["ma20"].iloc[i]; m60 = df["ma60"].iloc[i]
            pc = df["close"].iloc[i-1]; pm20 = df["ma20"].iloc[i-1]; pm60 = df["ma60"].iloc[i-1]
            if pd.notna(m20) and pd.notna(pm20) and pd.notna(m60) and pd.notna(pm60):
                if pc <= pm20 and c > m20 and m20 > m60:
                    trend_cross[idx] = 1; changed = True
                elif pc >= pm60 and c < m60 and m20 < m60:
                    trend_cross[idx] = 1; changed = True

            # ② 结构形成
            if df["top_structure"].iloc[i] == 1 or df["bottom_structure"].iloc[i] == 1:
                struct_form[idx] = 1; changed = True

            # ③ 钝化消失（纠错）
            if df.get("divergence_lost", pd.Series([0]*len(df))).iloc[i] == 1:
                div_lost[idx] = 1; changed = True

            if changed:
                n_changing[idx] += 1

    result_change = (trend_cross | struct_form | div_lost).astype(int)

    result = pd.DataFrame({
        "date": dates,
        "trend_cross": trend_cross,
        "struct_form": struct_form,
        "div_lost": div_lost,
        "result_change": result_change,
        "n_changing": n_changing.astype(int),
    })

    # 合并市况
    if mc_path and os.path.exists(mc_path):
        mc = pd.read_csv(mc_path)
        mc["date"] = pd.to_datetime(mc["date"])
        result = result.merge(mc[["date","condition"]], on="date", how="left")

    return result


def report(result: pd.DataFrame):
    """打印"不重要"统计报告"""
    total = len(result)
    changing = int(result["result_change"].sum())
    unchanging = total - changing

    print("=" * 70)
    print('"不重要"检测器 · 徐小明原文定义')
    print("=" * 70)
    print(f'\n  "不重要 = 不改变操作结果"')
    print(f'  操作结果 = 趋势突破/破位 + 结构形成 + 钝化消失')
    print()

    print(f"  总交易日:     {total}")
    print(f"  改变操作结果: {changing} ({changing/total*100:.1f}%) ← 需要决策")
    print(f"  不改变结果:   {unchanging} ({unchanging/total*100:.1f}%) ← 不重要")

    print(f"\n  改变来源:")
    srcs = [("趋势突破/破位","trend_cross"),("结构形成","struct_form"),("钝化消失纠错","div_lost")]
    for label, col in srcs:
        n = int(result[col].sum())
        print(f"    {label:<16} {n:>5}d ({n/total*100:>5.1f}%)")

    # 年度
    result["year"] = pd.to_datetime(result["date"]).dt.year
    print(f"\n  年度不重要占比:")
    for yr in sorted(result["year"].unique()):
        y = result[result["year"]==yr]
        t = len(y)
        ns = (y["result_change"]==0).sum()
        bar = "░"*(12 - ns*12//max(t,1)) + "█"*(ns*12//max(t,1))
        print(f"    {yr}: {ns:>3}/{t} ({ns/t*100:>5.0f}%) {bar}")

    # 市况
    if "condition" in result.columns:
        print(f"\n  不重要 × 市况:")
        for c in ["单边上升","单边下跌","震荡·有信号","震荡·无信号"]:
            sub = result[result["condition"]==c]
            t = len(sub)
            ns = (sub["result_change"]==0).sum()
            print(f"    {c:<14}: {t:>5}d → 不重要 {ns:>4}d ({ns/max(t,1)*100:.0f}%)")

    # 连续不重要
    streaks = [0]
    for v in result["result_change"]:
        if v == 0:
            streaks[-1] += 1
        else:
            streaks.append(0)
    print(f"\n  连续不重要: 最长 {max(streaks)} 天, ≥10天连续段 {sum(1 for s in streaks if s>=10)} 次")


if __name__ == "__main__":
    daily_path = os.path.join(DATA, "daily_ma_channels.csv")
    if not os.path.exists(daily_path):
        print("请先运行 scripts/fetch_data.py")
        sys.exit(1)

    mc_path = os.path.join(DATA, "market_condition_xu_v2.csv")
    result = detect_unimportant(daily_path, mc_path)
    report(result)

    out = os.path.join(DATA, "unimportant_daily.csv")
    result.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n→ {out}")
