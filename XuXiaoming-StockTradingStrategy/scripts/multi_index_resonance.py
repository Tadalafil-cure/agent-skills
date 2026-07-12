#!/usr/bin/env python3
"""
徐小明多指数通道共振分析

基于 v5 通道分类器的六指数输出，分析：
  - 多指数趋势共振（几大指数同向单边）
  - 指数分化（各走各的）
  - 六指数协调度

徐小明原文：
  "六大指数分化" → 降低权重，等合力
  "多指数多周期结构共振" → 最强信号

输出：
  - data/multi_index_resonance.csv — 每日六指数状态 + 共振/分化标记
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT = DATA_DIR / "market_condition_xu_v5.csv"
OUTPUT = DATA_DIR / "multi_index_resonance.csv"

SIX_INDICES = ["上证指数", "深证成指", "创业板指", "沪深300", "中证500"]
# 科创50 已移除——历史数据显示它永远是最后一个突破，共振等它等于浪费时间

def main():
    print("=" * 60)
    print("多指数通道共振分析")
    print("=" * 60)
    
    df = pd.read_csv(INPUT)
    
    # 找到所有可用指数
    available = [n for n in SIX_INDICES if n in df["index_name"].values]
    print(f"\n可用指数: {len(available)}/5")
    for n in SIX_INDICES:
        mark = "✓" if n in available else "✗"
        print(f"  {mark} {n}")
    
    # 按日期透视：每行是一个日期，每列是一个指数的状态
    pivot = df.pivot_table(
        index="date", 
        columns="index_name", 
        values="channel_state",
        aggfunc="first"
    )
    pivot_close = df.pivot_table(
        index="date",
        columns="index_name",
        values="close",
        aggfunc="first"
    )
    
    # 确保六指数列都存在
    for idx in SIX_INDICES:
        if idx not in pivot.columns:
            pivot[idx] = "无数据"
        if idx not in pivot_close.columns:
            pivot_close[idx] = np.nan
    
    pivot = pivot[SIX_INDICES]
    pivot_close = pivot_close[SIX_INDICES]
    
    n_days = len(pivot)
    
    # ── 每日共振分析 ──
    results = []
    
    for date_val in pivot.index:
        row = pivot.loc[date_val]
        
        # 统计各状态
        up_count = sum(1 for s in row if "单边_上升" in str(s))
        dn_count = sum(1 for s in row if "单边_下跌" in str(s))
        oscillation = sum(1 for s in row if "震荡" in str(s) or "转变期" in str(s))
        convergence_late = sum(1 for s in row if "收敛末期" in str(s))
        transition = sum(1 for s in row if "转变期" in str(s))
        no_data = sum(1 for s in row if "数据不足" in str(s) or "无数据" in str(s))
        
        valid = 5 - no_data
        
        # 共振判定（5指数体系，科创50已移除）
        if valid < 2:
            resonance = "数据不足"
            direction = ""
            strength = 0
        elif up_count >= 5:
            resonance = "强共振_上升"
            direction = "上升"
            strength = up_count / valid
        elif dn_count >= 5:
            resonance = "强共振_下跌"
            direction = "下跌"
            strength = dn_count / valid
        elif up_count >= 4:
            resonance = "偏多共振"
            direction = "偏上升"
            strength = up_count / valid
        elif dn_count >= 4:
            resonance = "偏空共振"
            direction = "偏下跌"
            strength = dn_count / valid
        elif up_count >= 3 and dn_count >= 2:
            resonance = "分化_偏多"
            direction = "分化"
            strength = max(up_count, dn_count) / valid
        elif dn_count >= 3 and up_count >= 2:
            resonance = "分化_偏空"
            direction = "分化"
            strength = max(up_count, dn_count) / valid
        elif oscillation >= 4 and (convergence_late + transition) >= 1:
            resonance = "震荡_接近切换"
            direction = "待突破"
            strength = oscillation / valid
        elif oscillation >= 4:
            resonance = "全面震荡"
            direction = "震荡"
            strength = oscillation / valid
        elif up_count >= 2 and dn_count >= 2:
            resonance = "严重分化"
            direction = "分化"
            strength = 0.3
        else:
            resonance = "混合"
            direction = "不明确"
            strength = max(up_count, dn_count, oscillation) / valid
        
        # 计算六指数平均收盘价变化（用于标注方向强度）
        closes = pivot_close.loc[date_val]
        
        results.append({
            "date": date_val,
            "上证指数": row.get("上证指数", ""),
            "深证成指": row.get("深证成指", ""),
            "创业板指": row.get("创业板指", ""),
            "沪深300": row.get("沪深300", ""),
            "中证500": row.get("中证500", ""),
            "up_count": up_count,
            "dn_count": dn_count,
            "oscillation": oscillation,
            "convergence_late": convergence_late,
            "transition": transition,
            "valid_count": valid,
            "resonance": resonance,
            "direction": direction,
            "strength": round(strength, 2),
        })
    
    out = pd.DataFrame(results)
    out.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\n✅ 输出: {OUTPUT} ({len(out)} 天)")
    
    # ── 统计摘要 ──
    print("\n" + "=" * 60)
    print("共振状态分布")
    print("=" * 60)
    
    resonance_counts = out["resonance"].value_counts()
    total = len(out)
    for state, cnt in resonance_counts.items():
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {state:16s}  {cnt:5d}  ({pct:5.1f}%)  {bar}")
    
    # ── 强势共振区间 ──
    print("\n" + "=" * 60)
    print("六指数共振区间 (≥5指数同向)")
    print("=" * 60)
    
    for direction, label in [("上升", "📈 强共振上升 (≥5指数)"), ("下跌", "📉 强共振下跌 (≥5指数)")]:
        subset = out[(out["resonance"].str.contains(f"强共振_{direction}"))].sort_values("date")
        if len(subset) == 0:
            print(f"\n  {label}: 无")
            continue
        
        print(f"\n  {label}:")
        groups = []
        group_start = subset.iloc[0]["date"]
        group_end = group_start
        for _, row in subset.iloc[1:].iterrows():
            if pd.Timestamp(row["date"]) - pd.Timestamp(group_end) <= pd.Timedelta(days=3):
                group_end = row["date"]
            else:
                if pd.Timestamp(group_end) - pd.Timestamp(group_start) >= pd.Timedelta(days=5):
                    groups.append((group_start, group_end))
                group_start = row["date"]
                group_end = row["date"]
        if pd.Timestamp(group_end) - pd.Timestamp(group_start) >= pd.Timedelta(days=5):
            groups.append((group_start, group_end))
        
        for gs, ge in groups:
            days = (pd.Timestamp(ge) - pd.Timestamp(gs)).days
            print(f"    {gs} ~ {ge}  ({days}天)")
    
    # ── 严重分化区间 ──
    print("\n" + "=" * 60)
    print("六指数严重分化区间 (≥2上升+≥2下跌)")
    print("=" * 60)
    
    divergence = out[out["resonance"] == "严重分化"].sort_values("date")
    print(f"\n  共 {len(divergence)} 天")
    # 找长段
    groups = []
    if len(divergence) > 0:
        group_start = divergence.iloc[0]["date"]
        group_end = group_start
        for _, row in divergence.iloc[1:].iterrows():
            if pd.Timestamp(row["date"]) - pd.Timestamp(group_end) <= pd.Timedelta(days=3):
                group_end = row["date"]
            else:
                if pd.Timestamp(group_end) - pd.Timestamp(group_start) >= pd.Timedelta(days=5):
                    groups.append((group_start, group_end))
                group_start = row["date"]
                group_end = row["date"]
        if pd.Timestamp(group_end) - pd.Timestamp(group_start) >= pd.Timedelta(days=5):
            groups.append((group_start, group_end))
    
    if groups:
        for gs, ge in groups:
            days = (pd.Timestamp(ge) - pd.Timestamp(gs)).days
            print(f"    {gs} ~ {ge}  ({days}天)")
    else:
        print("  无长段严重分化")
    
    # ── 关键节点六指数快照 ──
    print("\n" + "=" * 60)
    print("关键节点六指数快照")
    print("=" * 60)
    
    key_dates = [
        "2019-04-08", "2020-03-19", "2021-02-18", 
        "2022-04-27", "2024-02-05", "2024-09-24",
        "2024-10-08", "2025-04-07"
    ]
    
    for d_str in key_dates:
        row = out[out["date"].astype(str).str[:10] == d_str]
        if len(row) > 0:
            r = row.iloc[0]
            print(f"\n  {d_str}")
            print(f"  共振: {r['resonance']} (强度={r['strength']})")
            print(f"  上升:{int(r['up_count'])}  下跌:{int(r['dn_count'])}  震荡:{int(r['oscillation'])}")
            print(f"  上证: {r['上证指数']}")
            print(f"  深证: {r['深证成指']}")
            print(f"  创业: {r['创业板指']}")
            print(f"  HS300: {r['沪深300']}")
            print(f"  中证500: {r['中证500']}")


if __name__ == "__main__":
    main()
