#!/usr/bin/env python3
"""
序列失效分析：30%失败时，趋势/结构是否早已给出更高级别信号？
验证 徐小明: 趋势 > 结构 > 序列
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from structure_engine import process_structure

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
NAMES = {"sh000001":"上证","sz399001":"深证","sz399006":"创业板",
         "sh000688":"科创50","sh000300":"沪深300","sh000905":"中证500"}


def check_signal_context(code, sig_date, daily):
    df = daily[(daily["index_code"]==code) & (daily["date"]<=sig_date)].sort_values("date")
    if len(df) < 60:
        return None
    last = df.iloc[-1]
    ma20_up = bool(last["ma20_above_ma60"])
    price_above_ma20 = bool(last["above_ma20"])
    trend = "上升趋势" if (ma20_up and price_above_ma20) else \
            ("下降趋势" if (not price_above_ma20 and not ma20_up) else "纠缠")
    if len(df) >= 20:
        mom20 = (last["close"] - df.iloc[-20]["close"]) / df.iloc[-20]["close"] * 100
    else:
        mom20 = 0
    sub = df.copy()
    sub = process_structure(sub)
    last_s = sub.iloc[-1]
    has_top_struct = bool(last_s.get("top_structure", 0) or last_s.get("top_divergence", 0))
    has_bot_struct = bool(last_s.get("bottom_structure", 0) or last_s.get("bottom_divergence", 0))
    struct_state = int(last_s.get("structure_state", 0))
    return {"trend": trend, "mom20": round(mom20, 1),
            "has_top_struct": has_top_struct, "has_bot_struct": has_bot_struct,
            "struct_state": struct_state}


def main():
    daily = pd.read_csv(os.path.join(DATA, "daily_ma_channels.csv"))
    daily["date"] = pd.to_datetime(daily["date"])
    seq = pd.read_csv(os.path.join(DATA, "turn_sequence_events.csv"))
    seq["date"] = pd.to_datetime(seq["date"])
    mc = pd.read_csv(os.path.join(DATA, "market_condition_xu_v2.csv"))
    mc["date"] = pd.to_datetime(mc["date"])

    seq_day = seq[(seq["period"]=="日") & (seq["count"]>=8)].copy()

    results = []
    for _, evt in seq_day.iterrows():
        code = evt["index_code"]
        sig_date = evt["date"]
        direction = evt["direction"]
        df_idx = daily[(daily["index_code"]==code) & (daily["date"]<=sig_date)].sort_values("date")
        if len(df_idx) < 60:
            continue
        pos = len(df_idx) - 1
        close0 = df_idx["close"].iloc[pos]
        fut = daily[(daily["index_code"]==code) & (daily["date"]>sig_date) &
                    (daily["date"]<=sig_date+pd.Timedelta(days=15))].sort_values("date")
        if len(fut) < 5:
            continue
        if direction == "高":
            max_adverse = (fut["low"].min() - close0) / close0 * 100
            success = max_adverse <= -2
        else:
            max_adverse = (fut["high"].max() - close0) / close0 * 100
            success = max_adverse >= 2
        ctx = check_signal_context(code, sig_date, daily)
        if ctx is None:
            continue
        mc_row = mc[mc["date"]==sig_date]
        market_cond = mc_row["condition"].iloc[0] if len(mc_row) else "?"
        results.append({
            "date": sig_date, "code": code, "name": NAMES.get(code,code),
            "direction": direction, "count": evt["count"],
            "has_div": evt["has_divergence"],
            "max_adverse": round(max_adverse, 2),
            "success": success,
            **ctx, "market_cond": market_cond,
        })

    df_r = pd.DataFrame(results)

    print("=" * 80)
    print("序列失效分析：趋势 > 结构 > 序列 优先级验证")
    print("=" * 80)

    for direction, label in [("高", "高9后10天回调"), ("低", "低9后10天反弹")]:
        sub = df_r[df_r["direction"]==direction]
        fail = sub[~sub["success"]]
        ok = sub[sub["success"]]

        print(f"\n{'='*80}")
        print(f"{label}：成功 {len(ok)}次 vs 失败 {len(fail)}次 "
              f"({len(fail)/max(len(sub),1)*100:.0f}%)")

        print(f"\n  趋势环境分布:")
        print(f"  {'状态':<10} {'成功':>6} {'失败':>6} {'失败率':>8}")
        print(f"  {'-'*35}")
        for t in ["上升趋势", "下降趋势", "纠缠"]:
            ok_n = (ok["trend"]==t).sum()
            fail_n = (fail["trend"]==t).sum()
            rate = fail_n / max(ok_n+fail_n, 1) * 100
            print(f"  {t:<10} {ok_n:>6} {fail_n:>6} {rate:>7.0f}%")

        if direction == "高":
            strong_trend_fail = fail[fail["trend"]=="上升趋势"]
            print(f"\n  高9 + 上升趋势中失败: {len(strong_trend_fail)}次 — 趋势推翻序列")
            print(f"  平均前20日涨幅: {strong_trend_fail['mom20'].mean():+.1f}%")
            if len(strong_trend_fail) > 0:
                cases = []
                for _, r in strong_trend_fail.head(6).iterrows():
                    cases.append(
                        r["date"].strftime("%Y-%m-%d") + " "
                        + r["name"] + "(+" + str(int(r["mom20"])) + "%)"
                    )
                print("  案例:", ", ".join(cases))

            bot_struct_fail = fail[fail["has_bot_struct"]]
            bot_struct_ok = ok[ok["has_bot_struct"]]
            t = len(bot_struct_fail) + len(bot_struct_ok)
            print(f"\n  高9当天有底部结构（结构反对）: "
                  f"失败{len(bot_struct_fail)}次 / 成功{len(bot_struct_ok)}次 "
                  f"-> 失败率{len(bot_struct_fail)/max(t,1)*100:.0f}%")

        else:
            strong_trend_fail = fail[fail["trend"]=="下降趋势"]
            print(f"\n  低9 + 下降趋势中失败: {len(strong_trend_fail)}次 — 趋势推翻序列")
            if len(strong_trend_fail) > 0:
                cases = []
                for _, r in strong_trend_fail.head(6).iterrows():
                    cases.append(
                        r["date"].strftime("%Y-%m-%d") + " "
                        + r["name"] + "(" + str(int(r["mom20"])) + "%)"
                    )
                print("  案例:", ", ".join(cases))

            top_struct_fail = fail[fail["has_top_struct"]]
            top_struct_ok = ok[ok["has_top_struct"]]
            t = len(top_struct_fail) + len(top_struct_ok)
            print(f"\n  低9当天有顶部结构（结构反对）: "
                  f"失败{len(top_struct_fail)}次 / 成功{len(top_struct_ok)}次 "
                  f"-> 失败率{len(top_struct_fail)/max(t,1)*100:.0f}%")

        if direction == "高":
            opposed = fail[(fail["trend"]=="上升趋势") | fail["has_bot_struct"]]
            opposed_ok = ok[(ok["trend"]=="上升趋势") | ok["has_bot_struct"]]
        else:
            opposed = fail[(fail["trend"]=="下降趋势") | fail["has_top_struct"]]
            opposed_ok = ok[(ok["trend"]=="下降趋势") | ok["has_top_struct"]]
        total_opp = len(opposed) + len(opposed_ok)
        pct_opp = len(opposed)/max(total_opp,1)*100
        print(f"\n  ★ 趋势或结构反对时: 失败{len(opposed)}/{total_opp} ({pct_opp:.0f}%)")
        no_opp_ok = len(ok) - len(opposed_ok)
        no_opp_fail = len(fail) - len(opposed)
        print(f"    无反对时: 成功{no_opp_ok}/{no_opp_ok+no_opp_fail}")

    print(f"\n{'='*80}")
    print("钝化+9：失败率是否更低？")
    for direction in ["高", "低"]:
        sub = df_r[df_r["direction"]==direction]
        div = sub[sub["has_div"]]
        bare = sub[~sub["has_div"]]
        div_ok = div["success"].sum()
        bare_ok = bare["success"].sum()
        print(f"  {direction}9: 钝化+9 成功率 {div_ok}/{len(div)} "
              f"({div_ok/max(len(div),1)*100:.0f}%)  vs "
              f"裸 {bare_ok}/{len(bare)} ({bare_ok/max(len(bare),1)*100:.0f}%)")


if __name__ == '__main__':
    main()
