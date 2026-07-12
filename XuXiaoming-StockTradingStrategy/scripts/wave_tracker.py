#!/usr/bin/env python3
"""
浪型追踪引擎 · 简化版

徐小明用法（2025原文提炼）：
  1. 大周期定位：日线大3浪 → 主升浪判断
  2. 时间对称：浪1+浪2 ≈ 浪4+浪5 时间 → 预判转折窗口
  3. ABC调整：C浪低点 < A浪低点 → 确立调整浪
  4. 速度验证：反弹速度慢 → 倾向B浪而非新升浪

输出：
  - 上证指数的浪型标注（日线级别）
  - 时间对称预警
  - 配合结构信号的浪型确认
"""

import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))

DATA = os.path.join(os.path.dirname(__file__), "..", "data")

def detect_swings(df, min_bars=20):
    """
    检测主要高低点（基于MA20/60 + 局部极值）

    简化逻辑：在MA20/MA60趋势转换点附近找局部极值。
    """
    n = len(df)
    swings = []  # [(date, price, type:'high'|'low', confidence)]

    for i in range(min_bars, n - min_bars):
        close = df["close"].iloc[i]
        ma20 = df["ma20"].iloc[i]
        ma60 = df["ma60"].iloc[i]

        # 趋势转换点：MA20/MA60 交叉
        if i >= 2:
            prev_20_60 = int(df["ma20_above_ma60"].iloc[i-2])
            curr_20_60 = int(df["ma20_above_ma60"].iloc[i])

        # 局部高低点
        local_high = close
        local_low = close
        is_local_high = True
        is_local_low = True
        for j in range(i - min_bars // 2, i + min_bars // 2 + 1):
            if j < 0 or j >= n:
                continue
            if df["close"].iloc[j] > close + close * 0.02:
                is_local_high = False
            if df["close"].iloc[j] < close - close * 0.02:
                is_local_low = False

        if is_local_high and not pd.isna(ma20):
            swings.append({
                "date": df["date"].iloc[i],
                "close": close,
                "type": "high",
                "ma20": ma20,
                "ma60": ma60,
            })
        elif is_local_low and not pd.isna(ma20):
            swings.append({
                "date": df["date"].iloc[i],
                "close": close,
                "type": "low",
                "ma20": ma20,
                "ma60": ma60,
            })

    # 去重：同类型相邻的只保留极值
    if len(swings) < 2:
        return pd.DataFrame(swings)

    filtered = [swings[0]]
    for s in swings[1:]:
        last = filtered[-1]
        if s["type"] == last["type"]:
            if (s["type"] == "high" and s["close"] > last["close"]) or \
               (s["type"] == "low" and s["close"] < last["close"]):
                filtered[-1] = s  # 替换为更极端的
        else:
            # 过滤太近的（<10天）
            if len(filtered) >= 1 and abs((s["date"] - filtered[-1]["date"]).days) < 10:
                continue
            filtered.append(s)

    return pd.DataFrame(filtered)


def label_waves(swings_df, current_idx=None):
    """
    对检测到的高低点进行浪型标注。

    简化规则：
    - 上升浪：low→high，标为 {1,3,5} 或 {B}（如果是反弹）
    - 下降浪：high→low，标为 {2,4} 或 {A,C}

    实际使用需要人工辅助判断，这里只做初步标注。
    """
    if len(swings_df) < 3:
        return swings_df

    waves = []
    wave_labels = []

    # 简化：从最后一个低点开始，交替标注
    # 先确定当前方向
    last_swing = swings_df.iloc[-1]
    prev_swing = swings_df.iloc[-2]

    for i in range(len(swings_df)):
        s = swings_df.iloc[i]
        waves.append({
            "date": s["date"],
            "close": s["close"],
            "type": s["type"],
            "ma20": s.get("ma20", None),
            "ma60": s.get("ma60", None),
        })

    # 简化标注：最近5段波浪
    result = pd.DataFrame(waves)
    if len(result) >= 5:
        types = result["type"].tolist()
        # 从最后一个 low 开始标注
        labels = [""] * len(result)
        recent = result.tail(5).copy()
        # 尝试标注最近的5浪
        last_5_types = recent["type"].tolist()
        if last_5_types == ["low","high","low","high","low"]:
            labels[-5:] = ["浪1底","浪2顶?","浪3底?","浪4顶?","浪5底?"]
        elif last_5_types == ["high","low","high","low","high"]:
            labels[-5:] = ["浪1顶","浪2底","浪3顶","浪4底","浪5顶"]
        elif last_5_types[-3:] == ["high","low","high"]:
            labels[-3:] = ["A浪顶","B浪底","C浪顶?"]
        elif last_5_types[-3:] == ["low","high","low"]:
            labels[-3:] = ["A浪底","B浪顶","C浪底?"]

        result["label"] = labels
    else:
        result["label"] = ""

    return result


def compute_time_symmetry(waves_df):
    """
    计算浪段时间对称性。

    徐小明核心用法：
    - 浪1+浪2 ≈ 浪4+浪5 → 时间对称窗口
    - "3浪1+3浪2用了50天，3浪4+3浪5到今天49天" → 预判转折
    """
    if len(waves_df) < 5:
        return None

    # 取最近几个浪段
    recent = waves_df.tail(5)
    dates = recent["date"].tolist()

    symmetries = []

    # 计算相邻段的时间差
    for i in range(1, len(dates)):
        days = (dates[i] - dates[i-1]).days
        symmetries.append({
            "from": dates[i-1],
            "to": dates[i],
            "days": days,
            "label": recent["label"].iloc[i] if "label" in recent.columns else "",
        })

    # 检查对称性：浪1+浪2 vs 浪4+浪5
    if len(symmetries) >= 4:
        t12 = symmetries[0]["days"] + symmetries[1]["days"]
        t45 = symmetries[2]["days"] + symmetries[3]["days"]
        ratio = t45 / max(t12, 1)
        if 0.8 < ratio < 1.25:
            symmetries.append({
                "from": None,
                "to": None,
                "days": None,
                "label": f"⚡ 时间对称: 浪1+2={t12}d vs 浪4+5={t45}d (比值{ratio:.2f})",
            })

    return symmetries


def report(df, code="sh000001"):
    """浪型分析报告"""
    print(f"\n{'='*60}")
    print(f"浪型追踪 · {code}")
    print(f"{'='*60}")

    swings = detect_swings(df)
    print(f"\n  检测到 {len(swings)} 个主要高低点")

    # 列出最近10个
    recent = swings.tail(10)
    for _, s in recent.iterrows():
        marker = "▲" if s["type"] == "high" else "▼"
        print(f"    {s['date'].strftime('%Y-%m-%d')} {marker} {s['close']:.0f}")

    # 时间对称
    waves = label_waves(swings)
    syms = compute_time_symmetry(waves)
    if syms:
        print(f"\n  浪段时间:")
        for s in syms:
            if s["days"]:
                print(f"    {str(s['from'])[:10]} → {str(s['to'])[:10]}: {s['days']}d  {s['label']}")
            elif s["label"]:
                print(f"    {s['label']}")

    return swings, waves


if __name__ == "__main__":
    daily = pd.read_csv(os.path.join(DATA, "daily_ma_channels.csv"))
    daily["date"] = pd.to_datetime(daily["date"])

    # 上证指数
    sz = daily[daily["index_code"]=="sh000001"].sort_values("date").reset_index(drop=True)
    swings, waves = report(sz)

    out = os.path.join(DATA, "wave_labels.csv")
    waves.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n→ {out}")
