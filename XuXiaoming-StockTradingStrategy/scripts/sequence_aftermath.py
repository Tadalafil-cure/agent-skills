#!/usr/bin/env python3
"""序列9后效验证：高9→调整？低9→反弹？趋势/结构何时推翻序列"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from structure_engine import process_structure

DATA = os.path.join(os.path.dirname(__file__), "..", "data")

INDICES = ["sh000001","sz399001","sz399006","sh000688","sh000300","sh000905"]
NAMES = {"sh000001":"上证","sz399001":"深证","sz399006":"创业板","sh000688":"科创50","sh000300":"沪深300","sh000905":"中证500"}


def analyze_aftermath(events_df, direction, lookback_days=20):
    """序列后N日内的价格行为"""
    results = []
    for _, evt in events_df.iterrows():
        code = evt["index_code"]
        sig_date = evt["date"]
        sig_idx = daily[(daily["index_code"]==code) & (daily["date"]==sig_date)].index
        if len(sig_idx) == 0:
            continue
        sig_idx = sig_idx[0]

        df = daily[daily["index_code"]==code].sort_values("date").reset_index(drop=True)
        pos = df[df["date"]==sig_date].index
        if len(pos) == 0:
            continue
        pos = pos[0]

        close0 = df["close"].iloc[pos]

        if pos >= 10:
            trend_before = (df["close"].iloc[pos] - df["close"].iloc[pos-10]) / df["close"].iloc[pos-10] * 100
        else:
            trend_before = 0

        for window in [5, 10, 15, 20]:
            end = min(pos + window + 1, len(df))
            if end <= pos + 3:
                continue
            fut = df.iloc[pos+1:end]
            if direction == "高":
                max_dd = (fut["low"].min() - close0) / close0 * 100
            else:
                max_dd = (fut["high"].max() - close0) / close0 * 100

            results.append({
                "date": sig_date, "index_code": code, "index_name": NAMES.get(code, code),
                "direction": direction, "count": evt["count"],
                "has_div": evt["has_divergence"],
                "window": window, "max_move_pct": round(max_dd, 2),
                "trend_before_10d": round(trend_before, 1),
            })

    return pd.DataFrame(results)


def main():
    global daily
    daily = pd.read_csv(os.path.join(DATA, "daily_ma_channels.csv"))
    daily["date"] = pd.to_datetime(daily["date"])

    seq = pd.read_csv(os.path.join(DATA, "turn_sequence_events.csv"))
    seq["date"] = pd.to_datetime(seq["date"])
    seq_daily = seq[seq["period"] == "日"].copy()

    high9_after = analyze_aftermath(seq_daily[seq_daily["direction"]=="高"], "高")
    low9_after = analyze_aftermath(seq_daily[seq_daily["direction"]=="低"], "低")
    all_after = pd.concat([high9_after, low9_after], ignore_index=True)

    print("=" * 70)
    print("序列9后效验证：调整/反弹完成度")
    print("=" * 70)

    for direction, label, threshold in [("高", "高9后回调", -2), ("低", "低9后反弹", 2)]:
        sub = all_after[all_after["direction"] == direction]
        print(f"\n{label}（期望 {'回调≥2%' if direction=='高' else '反弹≥2%'}）:")
        print(f"{'窗口':>5} {'总信号':>6} {'达标':>6} {'达标率':>7} {'平均幅度':>8} {'钝+9达标率':>10}")
        print("-" * 50)
        for w in [5, 10, 15, 20]:
            wsub = sub[sub["window"] == w]
            total = len(wsub)
            if direction == "高":
                hit = (wsub["max_move_pct"] <= threshold).sum()
            else:
                hit = (wsub["max_move_pct"] >= threshold).sum()
            rate = hit / total * 100 if total else 0
            avg = wsub["max_move_pct"].mean()

            div_sub = wsub[wsub["has_div"] == True]
            div_total = len(div_sub)
            if direction == "高":
                div_hit = (div_sub["max_move_pct"] <= threshold).sum() if div_total else 0
            else:
                div_hit = (div_sub["max_move_pct"] >= threshold).sum() if div_total else 0
            div_rate = div_hit / div_total * 100 if div_total else 0

            print(f"{w:>5}天 {total:>6} {hit:>6} {rate:>6.0f}% {avg:>7.1f}% {div_rate:>9.0f}% ({div_total})")

    print(f"\n{'─' * 70}")
    print("趋势过强推翻序列（前10天涨/跌 >5%，序列被碾压）")
    for direction, cond in [("高", "trend_before_10d > 5"), ("低", "trend_before_10d < -5")]:
        sub = all_after[(all_after["direction"]==direction) & (all_after["window"]==10)]
        trend_override = sub[eval(f"sub.{cond}")]
        if direction == "高":
            valid = trend_override[trend_override["max_move_pct"] <= -2]
        else:
            valid = trend_override[trend_override["max_move_pct"] >= 2]

        print(f"\n{direction}9 + 前10天{'大涨' if direction=='高' else '大跌'} >5%: "
              f"{len(trend_override)}次, 仍回调≥2%: {len(valid)}次 ({len(valid)/max(len(trend_override),1)*100:.0f}%)")
        if len(valid) > 0:
            for _, r in valid.head(5).iterrows():
                print(f"  {r['date'].strftime('%Y-%m-%d')} {r['index_name']} "
                      f"前趋势{r['trend_before_10d']:+.1f}% → 后10天{r['max_move_pct']:+.1f}%")

    print(f"\n{'─' * 70}")
    print("钝化+9 vs 裸序列9：调整完成的时间差异（10天窗口）")
    for direction in ["高", "低"]:
        sub = all_after[(all_after["direction"]==direction) & (all_after["window"]==10)]
        bare = sub[~sub["has_div"]]
        div = sub[sub["has_div"]]
        bare_avg = bare["max_move_pct"].mean()
        div_avg = div["max_move_pct"].mean()
        print(f"  {direction}9: 裸序列 {len(bare)}次 平均{bare_avg:+.1f}%  |  "
              f"钝化+9 {len(div)}次 平均{div_avg:+.1f}%  "
              f"{'✓钝化+9更强' if abs(div_avg) > abs(bare_avg) else '≈相近'}")

    print(f"\n{'─' * 70}")
    print("高9后10天回调<1%（几乎无效）——趋势/结构推翻序列")
    high10 = all_after[(all_after["direction"]=="高") & (all_after["window"]==10)]
    weak = high10[high10["max_move_pct"] > -1].sort_values("max_move_pct", ascending=False)
    print(f"  共 {len(weak)} 次（占 {len(weak)/max(len(high10),1)*100:.0f}%）")
    for _, r in weak.head(8).iterrows():
        code = r["index_code"]
        d = r["date"]
        df_idx = daily[(daily["index_code"]==code) & (daily["date"]<=d)].sort_values("date")
        if len(df_idx) < 60:
            continue
        last = df_idx.iloc[-1]
        ts = "上升趋势" if last.get("ma20_above_ma60") and last.get("above_ma20") else "纠缠"
        print(f"  {d.strftime('%Y-%m-%d')} {r['index_name']:<6} "
              f"前趋势{r['trend_before_10d']:+.1f}% 后回调{r['max_move_pct']:+.1f}%  "
              f"市况:{ts}")


if __name__ == '__main__':
    main()
