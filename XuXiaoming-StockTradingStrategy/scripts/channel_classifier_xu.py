#!/usr/bin/env python3
"""
徐小明纯正通道+收敛发散分类器 v5.2

设计原则：只使用徐小明原文中出现过的概念
  - 短期/长期趋势线（MA20 / MA60）构成通道上下轨
  - 收盘价 vs 通道轨道 → 突破/破位
  - 两条均线间距变化 → 收敛/发散
  - 收敛末期 → 震荡即将切换单边的预判
  - 转变期 → 震荡结束到单边开始的过渡阶段

突破确认规则：
  - 普通情况：收盘价突破通道 + 持续 ≥5 天 → 单边
  - 例外：当前处于转变期/收敛末期/局部收敛（宽度连续缩小≥4天）+ 收盘价突破通道 → 当天即确认单边
    （对应徐小明"震荡告一段落，进入到单边市"）

主指数：深证成指（徐小明原文"拿深成指为标准"）
多指数共振：见 multi_index_resonance.py

不使用：ATR、ADX、Donchian/Keltner 通道、N日最高最低

原文引用：
  "趋势不能是一条线，而是一个通道"（2021-12-30）
  "由于两个趋势呈收敛状，我判断震荡市将告一段落"（2019-12-03）
  "拿深成指为标准"（2020-03-01）
  "难点在于预判单边和震荡的转变时期"（2019-11-24）
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# ── 配置 ──
DATA_DIR = Path(__file__).parent.parent / "data"
INPUT = DATA_DIR / "daily_ma_channels.csv"
OUTPUT = DATA_DIR / "market_condition_xu_v5.csv"  # 覆盖 v5，用 v5.1 逻辑

# 参数
LOOKBACK_CONVERGENCE = 250   # 收敛/发散判定的历史窗口
CONVERGENCE_PERCENTILE = 25  # 宽度 < 此百分位 → 低宽度（收敛态）
DIVERGENCE_PERCENTILE = 75   # 宽度 > 此百分位 → 高宽度（发散态）
CONVERGENCE_MIN_DAYS = 10    # 连续收敛 ≥ N 天 → 收敛末期
TRANSITION_LOOKBACK = 60     # 转变期判定：回头看多少天内有过收敛末期
SUSTAIN_MIN_DAYS = 5         # 单边突破后需持续 ≥N 天才确认（防假突破）


def classify_index(df: pd.DataFrame, index_name: str) -> pd.DataFrame:
    """对单个指数做纯徐小明通道分类"""
    df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    
    # ── 1. 计算通道 ──
    close = df["close"].values
    ma20 = df["ma20"].values
    ma60 = df["ma60"].values
    
    # 通道上下轨 = max(ma20, ma60) 为上轨, min(ma20, ma60) 为下轨
    upper = np.maximum(ma20, ma60)
    lower = np.minimum(ma20, ma60)
    
    # 通道宽度百分比
    channel_width_pct = np.full(n, np.nan)
    valid = (upper > 0) & (lower > 0) & (close > 0)
    channel_width_pct[valid] = (upper[valid] - lower[valid]) / close[valid] * 100
    
    # 趋势方向 (MA20 vs MA60)
    ma20_above_ma60 = ma20 > ma60  # True = 短期在长期上方 = 上升方向
    
    # ── 2. 收敛/发散判定 ──
    state = np.full(n, "震荡_中性", dtype=object)
    convergence_streak = np.zeros(n, dtype=int)
    
    for i in range(n):
        if i < LOOKBACK_CONVERGENCE:
            continue
        if pd.isna(channel_width_pct[i]):
            continue
        
        # 当前通道宽度在历史中的百分位
        hist_start = max(0, i - LOOKBACK_CONVERGENCE)
        hist_widths = channel_width_pct[hist_start:i]
        hist_widths = hist_widths[~np.isnan(hist_widths)]
        
        if len(hist_widths) < 60:
            continue
        
        pct_low = np.percentile(hist_widths, CONVERGENCE_PERCENTILE)
        pct_high = np.percentile(hist_widths, DIVERGENCE_PERCENTILE)
        current = channel_width_pct[i]
        
        if current < pct_low:
            state[i] = "震荡_收敛"
        elif current > pct_high:
            state[i] = "震荡_发散"
        # else: 保持 震荡_中性
    
    # ── 3. 收敛连续天数 ──
    for i in range(n):
        if state[i] == "震荡_收敛":
            convergence_streak[i] = convergence_streak[i-1] + 1 if i > 0 else 1
        else:
            convergence_streak[i] = 0
    
    # ── 3b. 短期收敛（局部）：通道宽度连续缩小 ≥5 天 ──
    # 不需要到历史极值——两条均线持续靠近即构成"收敛状"
    width_shrinking = np.zeros(n, dtype=bool)
    width_shrink_streak = np.zeros(n, dtype=int)
    for i in range(1, n):
        if pd.notna(channel_width_pct[i]) and pd.notna(channel_width_pct[i-1]):
            if channel_width_pct[i] < channel_width_pct[i-1]:
                width_shrink_streak[i] = width_shrink_streak[i-1] + 1
            else:
                width_shrink_streak[i] = 0
    
    # 合并：历史收敛 或 短期局部收敛
    local_converging = np.zeros(n, dtype=bool)
    for i in range(n):
        local_converging[i] = (state[i] == "震荡_收敛" or 
                               state[i] == "收敛末期" or 
                               width_shrink_streak[i] >= 4)  # 4天足够跨一个交易周
    
    # ── 4. 收敛末期 ──
    for i in range(n):
        if convergence_streak[i] >= CONVERGENCE_MIN_DAYS:
            state[i] = "收敛末期"
    
    # ── 5. 通道突破/破位 ──
    broke_upper = np.zeros(n, dtype=bool)
    broke_lower = np.zeros(n, dtype=bool)
    
    for i in range(1, n):
        if pd.isna(upper[i]) or pd.isna(lower[i]):
            continue
        # 收盘价突破上轨（注意：用当天收盘价 vs 当天轨道）
        broke_upper[i] = close[i] > upper[i]
        broke_lower[i] = close[i] < lower[i]
    
    # 单边确认：持续 ≥ SUSTAIN_MIN_DAYS 天突破
    upper_streak = np.zeros(n, dtype=int)
    lower_streak = np.zeros(n, dtype=int)
    for i in range(n):
        if broke_upper[i]:
            upper_streak[i] = upper_streak[i-1] + 1 if i > 0 else 1
        else:
            upper_streak[i] = 0
        if broke_lower[i]:
            lower_streak[i] = lower_streak[i-1] + 1 if i > 0 else 1
        else:
            lower_streak[i] = 0
    
    # ── 6. 转变期判定 ──
    # 过去 TRANSITION_LOOKBACK 天内有过"收敛末期" → 当前如果处于通道内 → "转变期"
    had_convergence_late = np.zeros(n, dtype=bool)
    for i in range(n):
        lookback_start = max(0, i - TRANSITION_LOOKBACK)
        for j in range(lookback_start, i+1):
            if convergence_streak[j] >= CONVERGENCE_MIN_DAYS:
                had_convergence_late[i] = True
                break
    
    # ── 7. 最终状态赋值 ──
    final_state = np.full(n, "", dtype=object)
    
    for i in range(n):
        if i < 60:  # 前60天数据不足
            final_state[i] = "数据不足"
            continue
        
        is_upper_break = upper_streak[i] >= SUSTAIN_MIN_DAYS
        is_lower_break = lower_streak[i] >= SUSTAIN_MIN_DAYS
        is_converging = state[i] == "震荡_收敛" or state[i] == "收敛末期"
        
        # 转变期/收敛末期 + 当天突破 → 立即确认（徐小明："震荡告一段落，进入到单边市"）
        # 局部收敛（宽度连续缩小≥5天）+ 当天突破 → 也立即确认
        # 普通情况仍需 5 天持续防假突破
        in_transition = had_convergence_late[i] or local_converging[i]
        immediate_up = in_transition and broke_upper[i] and not is_upper_break
        immediate_dn = in_transition and broke_lower[i] and not is_lower_break
        
        # 优先判断单边
        if is_upper_break or immediate_up:
            final_state[i] = "单边_上升"
        elif is_lower_break or immediate_dn:
            final_state[i] = "单边_下跌"
        elif state[i] == "收敛末期":
            final_state[i] = "收敛末期"
        elif had_convergence_late[i] and not is_upper_break and not is_lower_break:
            final_state[i] = "转变期"
        else:
            # 震荡子类型
            w = channel_width_pct[i]
            if pd.isna(w):
                final_state[i] = "震荡"
            else:
                final_state[i] = state[i]  # 震荡_收敛 / 震荡_发散 / 震荡_中性
    
    # ── 8. 构建输出 ──
    out = df[["date", "close"]].copy()
    out["index_name"] = index_name
    out["index_code"] = df["index_code"].iloc[0] if "index_code" in df.columns else ""
    out["ma20"] = ma20
    out["ma60"] = ma60
    out["channel_upper"] = upper
    out["channel_lower"] = lower
    out["channel_width_pct"] = np.round(channel_width_pct, 2)
    out["ma20_above_ma60"] = ma20_above_ma60.astype(int)
    out["broke_upper"] = broke_upper.astype(int)
    out["broke_lower"] = broke_lower.astype(int)
    out["upper_streak"] = upper_streak
    out["lower_streak"] = lower_streak
    out["convergence_streak"] = convergence_streak
    out["width_shrink_streak"] = width_shrink_streak
    out["channel_state"] = final_state
    # 标记 "立即确认" 的天数（转变期突破当天即确认）
    immediate_mask = np.zeros(n, dtype=bool)
    for i in range(n):
        if "单边" in str(final_state[i]):
            in_trans = had_convergence_late[i] or state[i] == "收敛末期"
            if in_trans and broke_upper[i] and upper_streak[i] < SUSTAIN_MIN_DAYS:
                immediate_mask[i] = True
            if in_trans and broke_lower[i] and lower_streak[i] < SUSTAIN_MIN_DAYS:
                immediate_mask[i] = True
    out["immediate_confirm"] = immediate_mask.astype(int)
    
    return out


def main():
    print("=" * 60)
    print("徐小明纯正通道+收敛发散分类器 v5.1")
    print("=" * 60)
    
    df = pd.read_csv(INPUT)
    # 处理 BOM
    df.columns = [c.lstrip("\ufeff") for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    
    # 找到所有指数
    if "index_code" in df.columns:
        codes = df["index_code"].unique()
    elif "index_name" in df.columns:
        codes = df["index_name"].unique()
    else:
        codes = ["上证指数"]  # fallback
    
    print(f"\n数据范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
    print(f"指数数量: {len(codes)}")
    print(f"总行数: {len(df)}")
    
    results = []
    for code in codes:
        if "index_code" in df.columns:
            sub = df[df["index_code"] == code].copy()
            name = sub["index_name"].iloc[0] if "index_name" in sub.columns else code
        else:
            sub = df.copy()
            name = code
        
        if len(sub) < 100:
            print(f"  {name}: 数据不足 (<100行), 跳过")
            continue
        
        print(f"  处理 {name} ({len(sub)} 天)...")
        try:
            res = classify_index(sub, name)
            results.append(res)
        except Exception as e:
            print(f"    ❌ 失败: {e}")
    
    if not results:
        print("无结果!")
        return
    
    all_out = pd.concat(results, ignore_index=True)
    all_out.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\n✅ 输出: {OUTPUT} ({len(all_out)} 行)")
    
    # ── 统计摘要 ──
    print("\n" + "=" * 60)
    print("全量统计摘要")
    print("=" * 60)
    
    for name in all_out["index_name"].unique():
        sub = all_out[all_out["index_name"] == name]
        # 排除"数据不足"
        sub_valid = sub[sub["channel_state"] != "数据不足"]
        
        print(f"\n── {name} ──")
        print(f"  有效天数: {len(sub_valid)}")
        
        counts = sub_valid["channel_state"].value_counts()
        total = len(sub_valid)
        for state, cnt in counts.items():
            pct = cnt / total * 100
            bar = "█" * int(pct / 2)
            print(f"  {state:12s}  {cnt:5d}  ({pct:5.1f}%)  {bar}")
        
        # 关键区间识别
        print(f"\n  关键区间:")
        
        # 找单边上升区间
        trend_up = sub_valid[sub_valid["channel_state"] == "单边_上升"]
        if len(trend_up) > 0:
            # 按日期连续性分组
            trend_up_sorted = trend_up.sort_values("date")
            groups = []
            group_start = trend_up_sorted.iloc[0]["date"]
            group_end = group_start
            for _, row in trend_up_sorted.iloc[1:].iterrows():
                if (row["date"] - group_end).days <= 3:
                    group_end = row["date"]
                else:
                    if (group_end - group_start).days >= 10:
                        groups.append((group_start, group_end))
                    group_start = row["date"]
                    group_end = row["date"]
            if (group_end - group_start).days >= 10:
                groups.append((group_start, group_end))
            
            for gs, ge in groups:
                days = (ge - gs).days
                print(f"    📈 单边上升: {gs.date()} ~ {ge.date()}  ({days}天)")
        
        trend_dn = sub_valid[sub_valid["channel_state"] == "单边_下跌"]
        if len(trend_dn) > 0:
            trend_dn_sorted = trend_dn.sort_values("date")
            groups = []
            group_start = trend_dn_sorted.iloc[0]["date"]
            group_end = group_start
            for _, row in trend_dn_sorted.iloc[1:].iterrows():
                if (row["date"] - group_end).days <= 3:
                    group_end = row["date"]
                else:
                    if (group_end - group_start).days >= 10:
                        groups.append((group_start, group_end))
                    group_start = row["date"]
                    group_end = row["date"]
            if (group_end - group_start).days >= 10:
                groups.append((group_start, group_end))
            
            for gs, ge in groups:
                days = (ge - gs).days
                print(f"    📉 单边下跌: {gs.date()} ~ {ge.date()}  ({days}天)")
        
        # 收敛末期区间
        conv_late = sub_valid[sub_valid["channel_state"] == "收敛末期"]
        if len(conv_late) > 0:
            conv_sorted = conv_late.sort_values("date")
            groups = []
            group_start = conv_sorted.iloc[0]["date"]
            group_end = group_start
            for _, row in conv_sorted.iloc[1:].iterrows():
                if (row["date"] - group_end).days <= 3:
                    group_end = row["date"]
                else:
                    if (group_end - group_start).days >= 5:
                        groups.append((group_start, group_end))
                    group_start = row["date"]
                    group_end = row["date"]
            if (group_end - group_start).days >= 5:
                groups.append((group_start, group_end))
            
            for gs, ge in groups:
                days = (ge - gs).days
                print(f"    ⚠️  收敛末期: {gs.date()} ~ {ge.date()}  ({days}天)")
    
    # ── 验证关键历史节点 ──
    print("\n" + "=" * 60)
    print("关键历史节点验证")
    print("=" * 60)
    
    key_dates = {
        "2019-01-04": "2440大底（徐小明底部结构形成）",
        "2019-04-08": "3288阶段顶",
        "2020-03-19": "2646疫情底",
        "2021-02-18": "3731大顶",
        "2022-04-27": "2863底",
        "2022-10-31": "2885底",
        "2024-02-05": "2635大底",
        "2024-09-24": "趋势突破（徐小明满仓日）",
        "2024-10-08": "3674阶段顶",
        "2025-04-07": "贸易战暴跌",
    }
    
    sh = all_out[all_out["index_name"].str.contains("上证", na=False)]
    if len(sh) == 0:
        sh = all_out  # 只有上证数据
    
    for date_str, desc in key_dates.items():
        d = pd.Timestamp(date_str)
        row = sh[sh["date"] == d]
        if len(row) > 0:
            state = row["channel_state"].iloc[0]
            close_val = row["close"].iloc[0]
            w = row["channel_width_pct"].iloc[0]
            c_streak = row["convergence_streak"].iloc[0]
            detail = f"close={close_val}, 宽度={w}%"
            if c_streak > 0:
                detail += f", 连续收敛{c_streak}天"
            print(f"  {date_str}  {desc:20s}  →  {state:12s}  ({detail})")


if __name__ == "__main__":
    main()
