#!/usr/bin/env python3
"""
徐小明市场状态日报 v2 · 深证主信号 + 五指数共振置信度

架构:
  L1 深证成指通道 → 方向判断 + 操作信号（有突破即行动）
  L2 五指数共振 → 置信度调整
    - 上证跟上 → +1★ (大盘确认)
    - 创业板跟上 → +1★ (成长确认)  
    - HS300跟上 → +1★ (机构确认)
    - 中证500跟上 → +1★ → 5指全共振
    - 科创50 已移除（永远是最后一名，等它等于浪费）

输出: daily_market_state.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_CHANNEL = DATA_DIR / "market_condition_xu_v5.csv"
INPUT_RESONANCE = DATA_DIR / "multi_index_resonance.csv"
OUTPUT = DATA_DIR / "daily_market_state.csv"

# 5 指数（科创50已移除）
FIVE = ["上证指数", "深证成指", "创业板指", "沪深300", "中证500"]


def calculate_confidence(sz_state, up_count, dn_count, resonance):
    """基于深证方向 + 共振确认度计算置信度"""
    base = 0
    
    if "单边_上升" in str(sz_state):
        base = 2  # 深证单边 = 2★打底
        if up_count >= 2: base += 1  # 上证/创业/HS300 至少有1个跟上
        if up_count >= 3: base += 1  # 3/5 = 偏共振
        if up_count >= 4: base += 1  # 4/5 = 强共振
        if up_count >= 5: base += 1  # 5/5 = 全共振
    elif "单边_下跌" in str(sz_state):
        base = 2
        if dn_count >= 2: base += 1
        if dn_count >= 3: base += 1
        if dn_count >= 4: base += 1
        if dn_count >= 5: base += 1
    elif "收敛末期" in str(sz_state):
        base = 3  # 即将切换
    elif "转变期" in str(sz_state):
        base = 2
    else:
        base = 2
    
    return min(base, 5)


def classify_combined(sz_state, up_count, dn_count, resonance):
    """综合判断"""
    if sz_state == "单边_上升":
        if up_count >= 5: return "强多_全共振"
        if up_count >= 4: return "强多_偏共振"
        if up_count >= 3: return "多头_3确认"
        if up_count >= 2: return "多头_初启"
        return "多头_独行"
    
    if sz_state == "单边_下跌":
        if dn_count >= 5: return "强空_全共振"
        if dn_count >= 4: return "强空_偏共振"
        if dn_count >= 3: return "空头_3确认"
        if dn_count >= 2: return "空头_初启"
        return "空头_独行"
    
    if sz_state == "收敛末期":
        return "收敛末期"
    
    if sz_state == "转变期":
        if up_count >= 2: return "转变_偏多"
        if dn_count >= 2: return "转变_偏空"
        return "转变_待定"
    
    if "震荡" in str(sz_state):
        return sz_state
    
    return sz_state


def main():
    print("=" * 60)
    print("徐小明市场状态日报 v2 · 深证主+五指共振")
    print("=" * 60)
    
    channel = pd.read_csv(INPUT_CHANNEL)
    resonance = pd.read_csv(INPUT_RESONANCE)
    
    sz = channel[channel["index_code"]=="sz399001"].copy()
    sz["date_str"] = sz["date"].astype(str).str[:10]
    resonance["date_str"] = resonance["date"].astype(str).str[:10]
    
    merged = sz.merge(
        resonance[["date_str","resonance","up_count","dn_count","oscillation","strength",
                    "上证指数","深证成指","创业板指","沪深300","中证500"]],
        on="date_str", how="left", suffixes=("","_r")
    )
    
    merged["confidence_val"] = merged.apply(
        lambda r: calculate_confidence(r["channel_state"], 
                                        r.get("up_count",0), r.get("dn_count",0),
                                        r.get("resonance","")), axis=1)
    
    merged["combined_state"] = merged.apply(
        lambda r: classify_combined(r["channel_state"],
                                     r.get("up_count",0), r.get("dn_count",0),
                                     r.get("resonance","")), axis=1)
    
    merged["confidence"] = merged["confidence_val"].apply(
        lambda v: "★" * int(v))
    
    # 输出
    out_cols = ["date","close",
                "channel_state","combined_state","confidence","confidence_val",
                "up_count","dn_count",
                "上证指数","深证成指","创业板指","沪深300","中证500",
                "channel_width_pct","width_shrink_streak","convergence_streak",
                "immediate_confirm",
                "ma20","ma60","channel_upper","channel_lower"]
    out_cols = [c for c in out_cols if c in merged.columns]
    out = merged[out_cols].copy()
    out.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\n✅ {OUTPUT} ({len(out)}天)")
    
    # 统计
    valid = out[out["combined_state"]!="数据不足"]
    print(f"\n综合判断分布:")
    for s,c in valid["combined_state"].value_counts().items():
        print(f"  {s:16s} {c:5d} ({c/len(valid)*100:5.1f}%)")
    
    # 关键节点
    print(f"\n关键节点:")
    for d,desc in [("2020-03-19","疫情底"),("2021-02-18","3731顶"),
                   ("2024-02-05","2635底"),("2024-09-24","924突破"),
                   ("2024-10-08","3674顶")]:
        r = out[out["date"].astype(str).str[:10]==d]
        if len(r)>0:
            rr = r.iloc[0]
            print(f"  {d} {desc:8s} → {rr['combined_state']:16s} {rr['confidence']} "
                  f"深证:{rr['channel_state']:10s} {int(rr['up_count'])}↑{int(rr['dn_count'])}↓")
    
    # 最新
    last = out.iloc[-1]
    print(f"\n最新: {last['date']} | {last['combined_state']} {last['confidence']} | "
          f"深证:{last['channel_state']} | {int(last['up_count'])}↑{int(last['dn_count'])}↓")


if __name__ == "__main__":
    main()
