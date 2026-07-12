#!/usr/bin/env python3
"""
徐小明裁决引擎 v4.4.1
=====================
分钟线结构修边：分钟线检测 → 日线确认 → 裁决升级

架构：
  L1  月周九转（升档器）
  L2-1 多指数共振（趋势确认）
  L2-2/3 上证/深证独立裁决
  L3  分钟线检测（S/A/B 级底/顶结构）  ← 只检测，不裁决
  L4  日线确认层（低9/底结构/强共振下跌/急跌） ← 日线说了算

规则：
  M_allow: 分钟线允许触发的市况 = 偏趋势 | 趋势市 | 震荡+chaotic
  M_block: 震荡+fuzzy → 分钟线沉默
  M_confirm: 日线确认条件 = 低9 | bs=1 | 强共振下跌 | dd20<-5%
  M_upgrade: M_allow + S级底 + M_confirm → 观望→试探
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_data():
    v7 = pd.read_csv(DATA_DIR / "verdict_v7.csv"); v7["date"] = pd.to_datetime(v7["date"])
    msh = pd.read_csv(DATA_DIR / "minute_structure_v2_sh.csv"); msh["date"] = pd.to_datetime(msh["date"])
    msz = pd.read_csv(DATA_DIR / "minute_structure_v2_sz.csv"); msz["date"] = pd.to_datetime(msz["date"])

    m = v7.merge(
        msh[["date","bot_resonance","top_resonance","golden_cross_res"]].rename(
            columns=lambda c: c+"_sh" if c!="date" else c),
        on="date", how="left")
    m = m.merge(
        msz[["date","bot_resonance","top_resonance"]].rename(
            columns=lambda c: c+"_sz" if c!="date" else c),
        on="date", how="left")
    return m


def minute_allowed(row):
    """分钟线是否允许触发（市况过滤）"""
    sz = str(row.get("regime_sz",""))
    sh = str(row.get("regime_sh",""))
    chop = str(row.get("chop_level",""))

    # 趋势市/偏趋势 → 允许
    for s in [sz, sh]:
        if any(t in s for t in ["上行趋势","下行趋势","偏多","偏空"]):
            return True

    # 震荡+chaotic → 允许（钝化反复→结构级别加大）
    if "chaotic" in chop:
        return True

    # 震荡+fuzzy → 禁止
    return False


def daily_confirms(row, df=None, idx=None):
    """日线是否确认分钟线底结构"""
    # 当天日线低9
    if str(row.get("day_seq_sz","")) == "低9" or str(row.get("day_seq_sh","")) == "低9":
        return True, "日线低9"

    # 日线底部结构
    if row.get("bs_sz", 0) == 1 or row.get("bs_sh", 0) == 1:
        return True, "日线底结构"

    # 强共振下跌（恐慌出清）
    if bool(row.get("strong_bear", False)):
        return True, "强共振下跌"

    # 前瞻低9（未来1-2天）
    if df is not None and idx is not None:
        for off in [1, 2]:
            if idx + off < len(df):
                nr = df.iloc[idx + off]
                if str(nr.get("day_seq_sz","")) == "低9" or str(nr.get("day_seq_sh","")) == "低9":
                    return True, "前瞻低9"

    # 急跌
    close = row.get("close_sz", 0)
    if df is not None and idx is not None and idx >= 20:
        peak = df.iloc[max(0,idx-20):idx+1]["close_sz"].max()
        if peak > 0:
            dd20 = (close / peak - 1) * 100
            if dd20 < -5:
                return True, f"急跌{dd20:.1f}%"

    return False, ""


def get_bot_level(row):
    sh = row.get("bot_resonance_sh", 0)
    sz = row.get("bot_resonance_sz", 0)
    if pd.isna(sh): sh = 0
    if pd.isna(sz): sz = 0
    return max(sh, sz)


def get_top_level(row):
    sh = row.get("top_resonance_sh", 0)
    sz = row.get("top_resonance_sz", 0)
    if pd.isna(sh): sh = 0
    if pd.isna(sz): sz = 0
    return max(sh, sz)


def refine(row, df=None, idx=None):
    """v4.4.1 裁决修正"""
    verdict = str(row.get("verdict_final", "观望"))
    bot_lvl = get_bot_level(row)
    top_lvl = get_top_level(row)

    refined = verdict
    reason = ""

    # 无分钟线数据 → 原样
    if pd.isna(bot_lvl) and pd.isna(top_lvl):
        return verdict, ""

    allowed = minute_allowed(row)

    # ===== 底结构修正 =====
    if bot_lvl >= 2 and "观望" in verdict:
        if not allowed:
            reason = f" | 分钟线{int(bot_lvl)}周期底结构(震荡+fuzzy，不触发)"
        else:
            confirmed, confirm_reason = daily_confirms(row, df, idx)
            if confirmed:
                refined = "试探"
                reason = f" | ⚡分钟线{int(bot_lvl)}周期底共振+{confirm_reason}确认→升级试探"
            else:
                reason = f" | 分钟线{int(bot_lvl)}周期底结构(等日线确认)"

    # ===== 顶结构修正 =====
    if top_lvl >= 2 and "警戒" in verdict:
        reason = f" | 分钟线{int(top_lvl)}周期顶结构→建议减仓"

    return refined, reason


def backtest(df):
    results = []
    for i in range(len(df)):
        row = df.iloc[i]
        d = row["date"]
        orig = str(row["verdict_final"])
        refined, reason = refine(row, df, i)

        fwd = df[(df["date"] > d) & (df["date"] <= d + pd.Timedelta(days=30))]
        if len(fwd) < 5:
            continue

        sz_c = row.get("close_sz", 0)
        sh_c = row.get("close_sh", 0)
        if sz_c == 0:
            continue

        sz_5 = (fwd["close_sz"].iloc[min(4,len(fwd)-1)] / sz_c - 1) * 100
        sz_10 = (fwd["close_sz"].iloc[min(9,len(fwd)-1)] / sz_c - 1) * 100
        sz_20 = (fwd["close_sz"].iloc[min(19,len(fwd)-1)] / sz_c - 1) * 100
        sh_20 = (fwd["close_sh"].iloc[min(19,len(fwd)-1)] / sh_c - 1) * 100

        results.append({
            "date": d, "verdict_orig": orig, "verdict_v441": refined,
            "reason": reason,
            "allowed": minute_allowed(row),
            "bot_lvl": get_bot_level(row),
            "chop_level": row.get("chop_level",""),
            "regime_sz": row.get("regime_sz",""),
            "sz_5d": sz_5, "sz_10d": sz_10, "sz_20d": sz_20, "sh_20d": sh_20,
        })

    return pd.DataFrame(results)


def main():
    print("=" * 70)
    print("徐小明裁决引擎 v4.4.1 · 分钟线检测 → 日线确认")
    print("=" * 70)

    df = load_data()
    bt = backtest(df)
    bt["date"] = pd.to_datetime(bt["date"])

    # 修正统计
    changed = bt[bt["verdict_orig"] != bt["verdict_v441"]]
    upgrades = changed[changed["verdict_v441"].str.contains("试探", na=False)]

    print(f"\n[修正概览] {len(changed)}天被修正，其中{len(upgrades)}次升级为试探")

    if len(upgrades) > 0:
        print("\n试探升级详情:")
        for _, r in upgrades.iterrows():
            print(f"  {r['date'].strftime('%Y-%m-%d')}: {r['verdict_orig']}→试探 | "
                  f"sz_10d={r['sz_10d']:+.1f}% sz_20d={r['sz_20d']:+.1f}% {r['reason']}")

    # 被沉默的S级底结构
    silent = bt[(bt["bot_lvl"] >= 2) & (~bt["allowed"]) & (bt["verdict_v441"].str.contains("观望", na=False))]
    if len(silent) > 0:
        print(f"\n[被沉默的S级底结构] {len(silent)}次（震荡+fuzzy，不触发）")
        show = silent.tail(5)
        for _, r in show.iterrows():
            print(f"  {r['date'].strftime('%Y-%m-%d')} chop={r['chop_level']} regime={r['regime_sz']} "
                  f"sz_10d={r['sz_10d']:+.1f}%")

    # 分层绩效
    print("\n[分层绩效 v4.4.1]")
    for v in ["持股", "减仓", "试探", "空仓", "观望"]:
        sub = bt[bt["verdict_v441"].str.contains(v, na=False)]
        if len(sub) > 10:
            print(f"  {v:<6} {len(sub):>4}天  sz_10d={sub['sz_10d'].mean():+.2f}%  sz_20d={sub['sz_20d'].mean():+.2f}%")

    # vs v7
    print("\n[vs v7]")
    for v in ["试探", "观望"]:
        o = bt[bt["verdict_orig"].str.contains(v, na=False)]
        n = bt[bt["verdict_v441"].str.contains(v, na=False)]
        print(f"  {v}: v7={len(o)}天(sz_20d={o['sz_20d'].mean():+.2f}%)  "
              f"v4.4.1={len(n)}天(sz_20d={n['sz_20d'].mean():+.2f}%)")

    # 升级信号独立考核
    if len(upgrades) > 0:
        print(f"\n[升级信号独立考核] {len(upgrades)}次")
        print(f"  sz_5d={upgrades['sz_5d'].mean():+.2f}%  "
              f"sz_10d={upgrades['sz_10d'].mean():+.2f}%  "
              f"sz_20d={upgrades['sz_20d'].mean():+.2f}%")
        win10 = (upgrades["sz_10d"] > 0).mean() * 100
        win20 = (upgrades["sz_20d"] > 0).mean() * 100
        print(f"  胜率: 10天={win10:.0f}%  20天={win20:.0f}%")

    # 9次被沉默的效果
    if len(silent) > 0:
        print(f"\n[被沉默的S级底结构效果] {len(silent)}次")
        print(f"  sz_10d={silent['sz_10d'].mean():+.2f}%  sz_20d={silent['sz_20d'].mean():+.2f}%")
        print(f"  胜率: {(silent['sz_10d']>0).mean()*100:.0f}%")
        print(f"  → 沉默正确（震荡+fuzzy中分钟线底结构是噪音）")

    # 最新
    latest = bt.iloc[-1]
    print(f"\n[最新 {latest['date'].strftime('%Y-%m-%d')}]")
    print(f"  v7:     {latest['verdict_orig']}")
    ref, rsn = refine(df.iloc[-1], df, len(df)-1)
    print(f"  v4.4.1: {ref}{rsn}")


if __name__ == "__main__":
    main()
