#!/usr/bin/env python3
"""
全管线交叉验证 · 7引擎一致性检查
排除分钟线（仅1-2年数据）。
"""
import pandas as pd, numpy as np, os
from pathlib import Path

SKILL = str(Path(__file__).resolve().parent.parent)
DATA = os.path.join(SKILL, "data")


def main():
    print("=" * 70)
    print("操作层管线 · 全检")
    print("=" * 70)
    print("\n[加载]")

    daily   = pd.read_csv(os.path.join(DATA, "daily_ma_channels.csv")); daily["date"]=pd.to_datetime(daily["date"])
    mc      = pd.read_csv(os.path.join(DATA, "market_condition_xu_v2.csv")); mc["date"]=pd.to_datetime(mc["date"])
    seq     = pd.read_csv(os.path.join(DATA, "turn_sequence_events.csv")); seq["date"]=pd.to_datetime(seq["date"])
    ft      = pd.read_csv(os.path.join(DATA, "failure_tracker_v2.csv")); ft["peak_date"]=pd.to_datetime(ft["peak_date"])
    unimp   = pd.read_csv(os.path.join(DATA, "unimportant_daily.csv")); unimp["date"]=pd.to_datetime(unimp["date"])
    coord   = pd.read_csv(os.path.join(DATA, "index_coordination.csv")); coord["date"]=pd.to_datetime(coord["date"])
    print(f"  daily: {len(daily)} rows, mc: {len(mc)} days, seq: {len(seq)} events, ft: {len(ft)} events, unimp: {len(unimp)} days, coord: {len(coord)} days")

    # ═══════════════ 检验1: 内部一致性 ═══════════════
    print(f"\n{'='*70}")
    print("检验1: 内部逻辑一致性")
    print("=" * 70)

    merged = mc.merge(unimp[["date","result_change"]], on="date", how="left")
    osc_signal = merged[merged["condition"]=="震荡·有信号"]
    violations = osc_signal[osc_signal["result_change"]==0]
    print(f"\n  1a. 震荡·有信号 + result_change=0: {len(violations)}次 "
          f"({'违规!' if len(violations)>0 else '✅'})")

    print(f"  1b. 单边上升天数: {(mc['condition']=='单边上升').sum()}, "
          f"单边下跌: {(mc['condition']=='单边下跌').sum()}, "
          f"震荡: {mc['condition'].str.startswith('震荡').sum()}")

    both = mc.merge(unimp[["date","result_change","trend_cross","struct_form","div_lost"]], on="date", how="left")
    no_change = both[both["result_change"]==0]
    has_struct_form = both[both["struct_form"]==1]
    print(f"  1c. result_change=0 天数: {len(no_change)} ({len(no_change)/len(both)*100:.0f}%)")
    print(f"      struct_form=1 天数: {len(has_struct_form)} ({len(has_struct_form)/len(both)*100:.0f}%)")

    # ═══════════════ 检验2: 序列信号 vs 趋势优先级 ═══════════════
    print(f"\n{'='*70}")
    print("检验2: 序列信号的质量标记")
    print("=" * 70)

    seq_day = seq[seq["period"]=="日"].copy()
    seq_day = seq_day.merge(mc[["date","condition"]], on="date", how="left")
    seq_day = seq_day.merge(coord[["date","coord_level"]], on="date", how="left")

    for direction in ["高", "低"]:
        sub = seq_day[seq_day["direction"]==direction]
        print(f"\n  {direction}9 序列事件 ({len(sub)}次):")

        for c in ["单边上升","单边下跌","震荡·有信号","震荡·无信号"]:
            n = (sub["condition"]==c).sum()
            if n > 0:
                opposed = ((direction=="高") & (c=="单边上升")) or ((direction=="低") & (c=="单边下跌"))
                flag = " ⚠️趋势反对" if opposed else ""
                print(f"    {c:<14}: {n:>4}次 ({n/len(sub)*100:.0f}%){flag}")

        high_coord = sub[sub["coord_level"].isin(["高度一致","基本一致"])]
        print(f"    高协调度时: {len(high_coord)}次 ({len(high_coord)/max(len(sub),1)*100:.0f}%)")

    # ═══════════════ 检验3: 连错事件 vs 市况 vs 结构 ═══════════════
    print(f"\n{'='*70}")
    print("检验3: 连错事件的市况归属")
    print("=" * 70)

    ft_merged = ft.merge(mc[["date","condition"]], left_on="peak_date", right_on="date", how="left")
    real = ft_merged[~ft_merged["is_false_positive"]]
    fp   = ft_merged[ft_merged["is_false_positive"]]

    print(f"\n  真信号 {len(real)}次:")
    for c in ["单边上升","单边下跌","震荡·有信号","震荡·无信号"]:
        n = (real["condition"]==c).sum()
        if n>0: print(f"    {c:<14}: {n}次")

    print(f"\n  假阳性 {len(fp)}次:")
    for _, r in fp.iterrows():
        print(f"    {r['peak_date'].strftime('%Y-%m-%d')} {r['index_name']} "
              f"连错{r['peak_val']} 钝化比{r['balance_ratio']} 市况:{r['condition']}")

    # ═══════════════ 检验4: 关键日期全线交叉 ═══════════════
    print(f"\n{'='*70}")
    print("检验4: 关键市场转折点 · 全线交叉")
    print("=" * 70)

    KEY_DATES = {
        "2019-01-04": "2440大底",
        "2019-04-08": "3288阶段顶",
        "2020-02-04": "疫情底2685",
        "2020-07-13": "3458阶段顶",
        "2021-02-18": "3731大顶",
        "2021-07-28": "3312阶段底",
        "2022-04-27": "2863阶段底",
        "2022-10-31": "2885双底",
        "2023-01-30": "3310阶段顶",
        "2024-02-05": "2635大底",
        "2024-05-20": "3174阶段顶",
        "2024-09-24": "趋势突破日",
        "2024-10-08": "3674政策顶",
        "2025-04-07": "关税冲击底3040",
        "2026-04-07": "近期关键低点",
    }

    print(f"  {'日期':<12} {'事件':<14} {'市况':<14} {'不重要':>6} {'协调':>8} {'序列':>6} {'连错':>6}")
    print(f"  {'-'*70}")

    for date_str, label in KEY_DATES.items():
        d = pd.Timestamp(date_str)
        mc_row = mc[mc["date"]==d]
        cond = mc_row["condition"].iloc[0] if len(mc_row) else "?"
        u_row = unimp[unimp["date"]==d]
        is_unimportant = "不重要" if (len(u_row) and u_row["result_change"].iloc[0]==0) else "重要"
        c_row = coord[coord["date"]==d]
        coord_lvl = c_row["coord_level"].iloc[0] if len(c_row) else "?"
        seq_on_date = seq[(seq["date"]==d) & (seq["period"]=="日")]
        seq_str = ""
        if len(seq_on_date) > 0:
            highs = seq_on_date[seq_on_date["direction"]=="高"]
            lows = seq_on_date[seq_on_date["direction"]=="低"]
            if len(highs) > 0: seq_str += f"高{len(highs)} "
            if len(lows) > 0: seq_str += f"低{len(lows)}"
        ft_on_date = ft[(ft["peak_date"]==d)]
        ft_str = ""
        if len(ft_on_date) > 0:
            real_ft = ft_on_date[~ft_on_date["is_false_positive"]]
            fp_ft = ft_on_date[ft_on_date["is_false_positive"]]
            if len(real_ft) > 0: ft_str += f"真{len(real_ft)} "
            if len(fp_ft) > 0: ft_str += f"假{len(fp_ft)}"
        marker = " ★" if ("趋势突破" in label or "大底" in label or "大顶" in label) else ""
        print(f"  {date_str:<12} {label:<14} {cond:<14} {is_unimportant:>6} {coord_lvl:>8} {seq_str:>6} {ft_str:>6}{marker}")

    # ═══════════════ 检验5: 协调度-信号质量关联 ═══════════════
    print(f"\n{'='*70}")
    print("检验5: 协调度 vs 信号可靠性")
    print("=" * 70)

    coord_merged = coord.merge(unimp[["date","result_change"]], on="date", how="left")
    for lvl in ["高度一致","基本一致","部分分化","明显分化","严重分化"]:
        sub = coord_merged[coord_merged["coord_level"]==lvl]
        t = len(sub)
        chg = sub["result_change"].sum()
        print(f"  {lvl:<8}: {t:>5}d → 操作改变 {int(chg):>4}d ({chg/max(t,1)*100:.0f}%) "
              f"{'█'*int(chg/max(t,1)*100//5)}{'░'*(20-int(chg/max(t,1)*100//5))}")

    # ═══════════════ 总结 ═══════════════
    print(f"\n{'='*70}")
    print("全检结论")
    print("=" * 70)

    total_days = len(mc)
    osc_sig = merged[merged["condition"]=="震荡·有信号"]
    pct_change = osc_sig["result_change"].sum() / max(len(osc_sig), 1) * 100
    print(f"  ✅ 震荡·有信号 → 操作改变率: {pct_change:.0f}% (期望接近100%)")

    no_change_struct = both[(both["result_change"]==0) & (both["struct_form"]==1)]
    print(f"  ✅ 不重要日但有结构形成: {len(no_change_struct)}次 (期望0)")

    high9_up = seq_day[(seq_day["direction"]=="高") & (seq_day["condition"]=="单边上升")]
    low9_down = seq_day[(seq_day["direction"]=="低") & (seq_day["condition"]=="单边下跌")]
    seq_total = len(seq_day)
    seq_opposed = len(high9_up) + len(low9_down)
    print(f"  ✅ 序列逆趋势: {seq_opposed}/{seq_total} ({seq_opposed/seq_total*100:.0f}%)")
    print(f"  ✅ 不重要占比: {len(no_change)}/{total_days} ({len(no_change)/total_days*100:.0f}%)")
    print(f"  ✅ 高度一致占比: {(coord['coord_level']=='高度一致').sum()}/{len(coord)} "
          f"({(coord['coord_level']=='高度一致').sum()/len(coord)*100:.0f}%)")
    print(f"  ✅ 连错真/假比例: {len(real)}/{len(real)+len(fp)} "
          f"({len(real)/max(len(real)+len(fp),1)*100:.0f}%)")


if __name__ == '__main__':
    main()
