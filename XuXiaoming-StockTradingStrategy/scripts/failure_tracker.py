#!/usr/bin/env python3
"""
连错追踪器 v2 · 六指数 + 结构信号过滤

MA20/60 双通道趋势信号 → 连错追踪 → 与结构引擎交叉验证。

过滤规则（针对假阳性）:
  连错≥4 且 连错期间 顶钝化次数/底钝化次数 超出 [1:3, 3:1] 范围
  → 视为单边结构积累（非均衡震荡）→ 标记为疑似假阳性

多指数共振:
  同一事件窗口内，≥4连错且通过过滤的指数数量
  → 共振指数越多，信号可信度越高
"""

import pandas as pd
import numpy as np
import os
import sys

# 动态导入 structure_engine
sys.path.insert(0, os.path.dirname(__file__))
from structure_engine import process_structure

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
INDICES = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300", "sh000905"]
INDEX_NAMES = {
    "sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指",
    "sh000688": "科创50", "sh000300": "沪深300", "sh000905": "中证500",
}


def track_single(df: pd.DataFrame, confirm_days: int = 20) -> pd.DataFrame:
    """MA20/60 双通道趋势信号 + 连错追踪（单指数）
    
    v3 修正：进入单边市后连错归零。连错是震荡市的特征。
    """
    n = len(df)
    signal = np.zeros(n)
    result = np.zeros(n)
    consecutive = np.zeros(n)
    fail_count = 0
    pending = 0
    pending_idx = -1
    pending_price = 0.0
    single_side_streak = 0  # 连续单边天数

    for i in range(1, n):
        c = df["close"].iloc[i]
        m20 = df["ma20"].iloc[i]
        m60 = df["ma60"].iloc[i]
        pc = df["close"].iloc[i - 1]
        pm20 = df["ma20"].iloc[i - 1]
        pm60 = df["ma60"].iloc[i - 1]

        # ── 单边检测：连续处于单边市则连错归零 ──
        if (c > m20 > m60) or (c < m20 < m60):
            single_side_streak += 1
        else:
            single_side_streak = 0
        
        # 连续5天在单边状态 → 趋势确认 → 连错计数器归零
        if single_side_streak >= 5 and fail_count > 0:
            fail_count = 0

        # 突破：收盘站上MA20，且MA20>MA60，无待确认信号
        if pc <= pm20 and c > m20 and m20 > m60 and pending == 0:
            signal[i] = 1
            pending = 1
            pending_idx = i
            pending_price = c

        # 破位：收盘跌破MA60，且MA20<MA60，无待确认信号
        elif pc >= pm60 and c < m60 and m20 < m60 and pending == 0:
            signal[i] = -1
            pending = -1
            pending_idx = i
            pending_price = c

        # 确认窗口到期
        if pending != 0 and i - pending_idx >= confirm_days:
            pct = (df["close"].iloc[i] - pending_price) / pending_price
            if pending == 1:
                if pct > 0.02:
                    result[pending_idx] = 1
                    fail_count = 0
                else:
                    result[pending_idx] = -1
                    fail_count += 1
            else:
                if pct < -0.02:
                    result[pending_idx] = 1
                    fail_count = 0
                else:
                    result[pending_idx] = -1
                    fail_count += 1
            pending = 0

        consecutive[i] = fail_count

    df["trend_signal"] = signal.astype(int)
    df["signal_result"] = result.astype(int)
    df["consecutive_failures"] = consecutive.astype(int)
    return df


def extract_streaks(df: pd.DataFrame) -> list[dict]:
    """提取连错≥4的峰值事件"""
    streaks = []
    cf = df["consecutive_failures"].values
    n = len(cf)
    i = 1
    while i < n - 1:
        if cf[i] >= 4 and cf[i + 1] < cf[i]:
            # 峰值点，回溯开始位置
            peak_val = int(cf[i])
            start = i
            while start > 0 and cf[start - 1] > 0 and cf[start - 1] < cf[start]:
                start -= 1
            # 找到fail_count从1开始的点
            streak_start = start
            while streak_start > 0 and cf[streak_start] > 0:
                streak_start -= 1
            streak_start += 1

            streaks.append({
                "peak_date": df["date"].iloc[i],
                "peak_val": peak_val,
                "start_idx": streak_start,
                "end_idx": i,
                "start_date": df["date"].iloc[streak_start],
                "end_date": df["date"].iloc[i],
            })
            i = i + 1
        else:
            i += 1
    return streaks


def analyze_structure_during_streak(
    df: pd.DataFrame, streaks: list[dict]
) -> list[dict]:
    """
    对每条连错事件，分析连错期间的结构信号。
    返回事件列表，附加字段:
      - top_div_count: 连错期间顶钝化天数
      - bot_div_count: 连错期间底钝化天数
      - top_struct_count: 顶部结构形成次数
      - bot_struct_count: 底部结构形成次数
      - balance_ratio: 顶/底钝化比（max/min）
      - is_false_positive: 是否疑似假阳性
    """
    enriched = []
    for s in streaks:
        window = df.iloc[s["start_idx"]:s["end_idx"] + 1]
        top_div = int(window["top_divergence"].sum()) if "top_divergence" in window else 0
        bot_div = int(window["bottom_divergence"].sum()) if "bottom_divergence" in window else 0
        top_struct = int(window["top_structure"].sum()) if "top_structure" in window else 0
        bot_struct = int(window["bottom_structure"].sum()) if "bottom_structure" in window else 0

        # 钝化比（顶/底），避免除0
        if bot_div > 0 and top_div > 0:
            balance_ratio = max(top_div, bot_div) / min(top_div, bot_div)
        elif top_div == 0 and bot_div == 0:
            balance_ratio = 1.0
        else:
            balance_ratio = 999.0  # 极不平衡

        # 假阳性判定：钝化比 > 3 且 连错期间结构形成次数极偏
        is_fp = False
        if balance_ratio > 3:
            total_struct = top_struct + bot_struct
            if total_struct > 0:
                struct_bias = max(top_struct, bot_struct) / max(top_struct + bot_struct, 1)
                if struct_bias > 0.8:  # 80%以上结构信号是单向的
                    is_fp = True

        s_enc = {**s}
        s_enc.update({
            "top_div_count": top_div,
            "bot_div_count": bot_div,
            "top_struct_count": top_struct,
            "bot_struct_count": bot_struct,
            "balance_ratio": round(balance_ratio, 1),
            "is_false_positive": is_fp,
        })
        enriched.append(s_enc)
    return enriched


def run_structure_integrated(daily_path: str):
    """六指数全量：连错追踪 + 结构交叉验证"""
    daily = pd.read_csv(daily_path)
    daily["date"] = pd.to_datetime(daily["date"])

    all_streaks = []
    index_summary = []

    for code in INDICES:
        df = daily[daily["index_code"] == code].copy().reset_index(drop=True)
        if df.empty:
            continue

        name = INDEX_NAMES.get(code, code)

        # 跑结构引擎
        df = process_structure(df)

        # 跑连错追踪
        df = track_single(df)

        # 提取≥4连错峰值
        streaks = extract_streaks(df)

        # 结构交叉
        enriched = analyze_structure_during_streak(df, streaks)

        n_signals = int((df["trend_signal"] != 0).sum())
        max_fail = int(df["consecutive_failures"].max())
        n_streaks = len(enriched)
        n_fp = sum(1 for s in enriched if s["is_false_positive"])
        n_real = n_streaks - n_fp

        index_summary.append({
            "index_code": code,
            "index_name": name,
            "n_signals": n_signals,
            "max_fail": max_fail,
            "n_streaks_ge4": n_streaks,
            "n_false_positive": n_fp,
            "n_real": n_real,
        })

        for s in enriched:
            s["index_code"] = code
            s["index_name"] = name
        all_streaks.extend(enriched)

    return all_streaks, index_summary


def report(all_streaks: list[dict], index_summary: list[dict]):
    """打印完整报告"""
    print("=" * 80)
    print("连错追踪 v2 · 六指数 + 结构信号过滤")
    print("=" * 80)

    # 汇总表
    print(f"\n{'指数':<10} {'信号总数':>8} {'最大连错':>8} {'≥4事件':>8} {'假阳性':>6} {'真信号':>6}")
    print("-" * 55)
    for r in index_summary:
        print(f"{r['index_name']:<10} {r['n_signals']:>8} {r['max_fail']:>8} "
              f"{r['n_streaks_ge4']:>8} {r['n_false_positive']:>6} {r['n_real']:>6}")

    # 假阳性详情
    fp_events = [s for s in all_streaks if s["is_false_positive"]]
    if fp_events:
        print(f"\n{'─' * 80}")
        print(f"疑似假阳性事件（{len(fp_events)} 次）—— 连错期间结构极度单向")
        print(f"{'指数':<10} {'连错':>6} {'峰值日期':<14} {'顶钝':>6} {'底钝':>6} {'钝化比':>8} {'顶结构':>6} {'底结构':>6}")
        print("-" * 75)
        for s in sorted(fp_events, key=lambda x: x["peak_date"]):
            print(f"{s['index_name']:<10} {s['peak_val']:>6} "
                  f"{s['peak_date'].strftime('%Y-%m-%d'):<14} "
                  f"{s['top_div_count']:>6} {s['bot_div_count']:>6} "
                  f"{s['balance_ratio']:>8.1f} "
                  f"{s['top_struct_count']:>6} {s['bot_struct_count']:>6}")

    # 真信号详情
    real_events = [s for s in all_streaks if not s["is_false_positive"]]
    if real_events:
        print(f"\n{'─' * 80}")
        print(f"通过过滤的事件（{len(real_events)} 次）—— 结构均衡的震荡积累")
        print(f"{'指数':<10} {'连错':>6} {'峰值日期':<14} {'顶钝':>6} {'底钝':>6} {'钝化比':>8}")
        print("-" * 55)
        for s in sorted(real_events, key=lambda x: x["peak_date"]):
            print(f"{s['index_name']:<10} {s['peak_val']:>6} "
                  f"{s['peak_date'].strftime('%Y-%m-%d'):<14} "
                  f"{s['top_div_count']:>6} {s['bot_div_count']:>6} "
                  f"{s['balance_ratio']:>8.1f}")

    # 多指数共振
    from collections import defaultdict
    EVENTS = {
        "2019Q4→2020Q1": ("2019-09-01", "2020-01-31"),
        "2020疫情V反": ("2020-01-15", "2020-04-30"),
        "2020牛→2021震荡": ("2020-11-01", "2021-03-31"),
        "2022熊市下跌": ("2021-12-01", "2022-06-30"),
        "2023全年震荡": ("2023-01-01", "2023-12-31"),
        "2024见底→9/24": ("2024-02-01", "2024-10-31"),
        "2025牛→调整": ("2025-04-01", "2025-08-31"),
    }

    print(f"\n{'─' * 80}")
    print("多指数共振度（≥4连错且通过过滤的指数数量）")
    print(f"{'事件':<24} {'共振指数':>12} {'指数列表'}")
    print("-" * 70)

    for evt, (start, end) in EVENTS.items():
        matched = []
        for code in INDICES:
            for s in real_events:
                if s["index_code"] == code and not s["is_false_positive"]:
                    d = s["peak_date"].strftime("%Y-%m-%d")
                    if start <= d <= end:
                        matched.append(INDEX_NAMES.get(code, code))
                        break
        names = ", ".join(matched[:6]) if matched else "无"
        print(f"{evt:<24} {len(matched):>6}/6     {names}")

    # 保存
    out = os.path.join(DATA_DIR, "failure_tracker_v2.csv")
    pd.DataFrame(all_streaks).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n→ 事件明细: {out}")

    out_sum = os.path.join(DATA_DIR, "failure_tracker_v2_summary.csv")
    pd.DataFrame(index_summary).to_csv(out_sum, index=False, encoding="utf-8-sig")
    print(f"→ 汇总:     {out_sum}")


if __name__ == "__main__":
    daily_path = os.path.join(DATA_DIR, "daily_ma_channels.csv")
    if not os.path.exists(daily_path):
        print("请先运行 scripts/fetch_data.py")
        sys.exit(1)

    all_streaks, index_summary = run_structure_integrated(daily_path)
    report(all_streaks, index_summary)
