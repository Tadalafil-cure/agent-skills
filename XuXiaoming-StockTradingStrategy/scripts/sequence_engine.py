#!/usr/bin/env python3
"""
九转序列引擎 · 徐小明版

基于汤姆·迪马克 TD Sequential，徐小明的核心用法：

定义:
  - 高9: 连续9根K线的收盘价 > 4根前的收盘价 → 卖出序列（预判顶部）
  - 低9: 连续9根K线的收盘价 < 4根前的收盘价 → 买入序列（预判底部）
  - 相等时序列断裂（counter归零）
  - 8-10 均为有效序列值（徐小明原文"序列上8、9、10都是有效序列"）

优先级: 趋势 > 结构 > 序列（序列不是交易规则，是辅助判断）

周期评分（徐小明原文）:
  - 月线: 最高分（"几年才一次"）→ 大底/大顶
  - 周线: 高分
  - 日线: 第二高分
  - 120min: 最高分（分钟线里）

增强信号（原文用法）:
  - 钝化+9: 同周期内钝化状态 + 序列9 → 更强
  - 多周期共振: 日线+周线+月线序列同在 → 级别放大
  - 多指数共振: ≥3个指数同时出现同向序列 → 更可靠

═══ 交叉分析原则（避免单指标陷阱） ═══

序列出信号 ≠ 可以操作。必须交叉验证趋势和结构：

  【趋势推翻序列】
  - 趋势方向明确时（MA20>MA60 且 价格>MA20 或 反之）
    → 序列要让位。徐小明原文："序列的缺点就是丢趋势，
       一个趋势性的行情，序列几乎都是不对的"
  - 回测：30%的序列失效中，60%发生在逆趋势场景
  - 高9 + 上升趋势 → 35%放弃率；低9 + 下降趋势 → 38%放弃率

  【结构增强序列】
  - 趋势不反对时，看结构是否共振
  - 钝化+9（同周期）→ 调整级别更大、更可信
  - 徐小明原文："上升趋势里的序列高9最好能够配合结构"

  【三层过滤决策链】
  ① 趋势层：趋势方向 vs 序列方向 → 同向则继续，反向则降权
  ② 结构层：有无钝化/结构形成 → 有则增强，无则观望
  ③ 序列层：序列本身的有效性（8-10有效、高分周期优先）

  【典型场景】
  - 震荡市 + 高9 + 有顶部钝化 → 高可信，准备减仓
  - 上升趋势 + 高9 + 无结构 → 低可信，"序列属于小聪明，趋势是大智慧"
  - 下降趋势 + 低9 + 底部结构 → 可信反弹，但仅限反弹不是反转
  - 无趋势无结构 + 序列 → "随缘"，不作为操作依据
"""

import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from structure_engine import process_structure

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

INDICES = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300", "sh000905"]
INDEX_NAMES = {
    "sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指",
    "sh000688": "科创50", "sh000300": "沪深300", "sh000905": "中证500",
}

PERIOD_SCORE = {"月": 10, "周": 8, "日": 6}


def calc_turn_sequence(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算九转序列（单指数单周期）。

    返回 df 附加字段:
      - turn_high_count: 当前高序列计数（1-9+）
      - turn_low_count:  当前低序列计数
      - turn_high_9:     高9信号（count >= 8）
      - turn_low_9:      低9信号
      - turn_high_streak: 高序列持续天数
      - turn_low_streak:  低序列持续天数
    """
    n = len(df)
    h_count = np.zeros(n, dtype=int)
    l_count = np.zeros(n, dtype=int)
    h_streak = np.zeros(n, dtype=int)
    l_streak = np.zeros(n, dtype=int)

    hc = 0
    lc = 0
    hs = 0
    ls = 0

    for i in range(n):
        if i < 4:
            continue

        c_now = df["close"].iloc[i]
        c_4ago = df["close"].iloc[i - 4]

        if c_now > c_4ago:
            hc += 1
            lc = 0
            hs += 1
            ls = 0
        elif c_now < c_4ago:
            lc += 1
            hc = 0
            ls += 1
            hs = 0
        else:
            hc = 0
            lc = 0
            hs = 0
            ls = 0

        h_count[i] = hc
        l_count[i] = lc
        h_streak[i] = hs
        l_streak[i] = ls

    df["turn_high_count"] = h_count
    df["turn_low_count"] = l_count
    df["turn_high_9"] = (h_count >= 8).astype(int)
    df["turn_low_9"] = (l_count >= 8).astype(int)
    df["turn_high_streak"] = h_streak
    df["turn_low_streak"] = l_streak
    return df


def detect_divergence_plus_nine(df: pd.DataFrame) -> pd.DataFrame:
    """钝化+9 增强信号检测（仅日线调用，需要先 process_structure）"""
    n = len(df)
    if "top_divergence" not in df.columns:
        return df

    div_plus_high9 = np.zeros(n, dtype=int)
    div_plus_low9 = np.zeros(n, dtype=int)

    for i in range(n):
        in_div = df["structure_state"].iloc[i] in [1, 2]
        if in_div:
            w_start = max(0, i - 1)
            w_end = min(n, i + 2)
            w_h9 = df["turn_high_9"].iloc[w_start:w_end].max()
            w_l9 = df["turn_low_9"].iloc[w_start:w_end].max()
            w_tdiv = df["top_divergence"].iloc[w_start:w_end].max()
            w_bdiv = df["bottom_divergence"].iloc[w_start:w_end].max()
            if w_h9 == 1 and w_tdiv == 1:
                div_plus_high9[i] = 1
            if w_l9 == 1 and w_bdiv == 1:
                div_plus_low9[i] = 1

    df["div_plus_high9"] = div_plus_high9
    df["div_plus_low9"] = div_plus_low9
    return df


def build_sequence_for_all(daily_path: str) -> dict:
    """日/周/月三周期六指数全量九转序列"""
    periods = {
        "daily": os.path.join(DATA_DIR, "daily_ma_channels.csv"),
        "weekly": os.path.join(DATA_DIR, "weekly_ma_channels.csv"),
        "monthly": os.path.join(DATA_DIR, "monthly_ma_channels.csv"),
    }

    results = {}
    for period_name, path in periods.items():
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"])
        all_frames = []
        for code in INDICES:
            sub = df[df["index_code"] == code].copy().reset_index(drop=True)
            if sub.empty or len(sub) < 10:
                continue
            sub = calc_turn_sequence(sub)
            if period_name == "daily":
                sub = process_structure(sub)
                sub = detect_divergence_plus_nine(sub)
            all_frames.append(sub)
        if all_frames:
            results[period_name] = pd.concat(all_frames, ignore_index=True)
    return results


def _extract_streak_events(sub: pd.DataFrame, code: str, period_label: str) -> list[dict]:
    """从单指数序列中提取每个序列段的触发事件（去重）"""
    events = []
    n = len(sub)
    i = 0
    while i < n:
        hc = int(sub["turn_high_count"].iloc[i])
        lc = int(sub["turn_low_count"].iloc[i])

        if hc >= 8:
            j = i + 1
            while j < n and int(sub["turn_high_count"].iloc[j]) > int(sub["turn_high_count"].iloc[j - 1]):
                j += 1
            # 取 count=9 那天，不存在则取起始日
            signal_idx = i
            for k in range(i, min(j, n)):
                if int(sub["turn_high_count"].iloc[k]) == 9:
                    signal_idx = k
                    break
            row = sub.iloc[signal_idx]
            events.append({
                "date": row["date"], "index_code": code,
                "index_name": INDEX_NAMES.get(code, code),
                "period": period_label, "direction": "高",
                "count": int(row["turn_high_count"]),
                "score": PERIOD_SCORE.get(period_label, 5),
                "has_divergence": bool(row.get("div_plus_high9", 0)),
            })
            i = j
        elif lc >= 8:
            j = i + 1
            while j < n and int(sub["turn_low_count"].iloc[j]) > int(sub["turn_low_count"].iloc[j - 1]):
                j += 1
            signal_idx = i
            for k in range(i, min(j, n)):
                if int(sub["turn_low_count"].iloc[k]) == 9:
                    signal_idx = k
                    break
            row = sub.iloc[signal_idx]
            events.append({
                "date": row["date"], "index_code": code,
                "index_name": INDEX_NAMES.get(code, code),
                "period": period_label, "direction": "低",
                "count": int(row["turn_low_count"]),
                "score": PERIOD_SCORE.get(period_label, 5),
                "has_divergence": bool(row.get("div_plus_low9", 0)),
            })
            i = j
        else:
            i += 1
    return events


def analyze_sequence_events(results: dict) -> list[dict]:
    """提取所有序列≥8的触发事件（按序列段去重）"""
    all_events = []
    for period_name, df in results.items():
        period_label = {"daily": "日", "weekly": "周", "monthly": "月"}[period_name]
        for code in INDICES:
            sub = df[df["index_code"] == code].sort_values("date")
            if sub.empty:
                continue
            all_events.extend(_extract_streak_events(sub, code, period_label))
    return all_events


def compute_resonance(events: list[dict]) -> pd.DataFrame:
    """共振分析：同日期同方向多指数/多周期聚合"""
    if not events:
        return pd.DataFrame()
    df = pd.DataFrame(events)
    df["date"] = pd.to_datetime(df["date"])

    grouped = df.groupby(["date", "direction"]).agg(
        n_indices=("index_code", "nunique"),
        indices=("index_name", lambda x: ", ".join(sorted(set(x)))),
        periods=("period", lambda x: ", ".join(sorted(set(x)))),
        n_periods=("period", "nunique"),
        max_count=("count", "max"),
        avg_score=("score", "mean"),
        has_div=("has_divergence", "max"),
    ).reset_index()

    grouped = grouped[(grouped["n_indices"] >= 2) | (grouped["n_periods"] >= 2)]
    grouped = grouped.sort_values(["n_indices", "n_periods", "avg_score"],
                                   ascending=[False, False, False])
    return grouped


def report(results: dict):
    """打印完整报告"""
    events = analyze_sequence_events(results)
    resonance = compute_resonance(events)

    print("=" * 80)
    print("九转序列引擎 · 徐小明版")
    print("=" * 80)

    # 信号统计（去重后）
    from collections import Counter
    for period_name in ["daily", "weekly", "monthly"]:
        if period_name not in results:
            continue
        label_map = {"daily": "日", "weekly": "周", "monthly": "月"}
        label = label_map[period_name]
        pe = [e for e in events if e["period"] == label]
        by_idx = Counter()
        by_idx_div = Counter()
        by_idx_low = Counter()
        by_idx_low_div = Counter()
        for e in pe:
            key = e["index_name"]
            if e["direction"] == "高":
                by_idx[key] += 1
                if e["has_divergence"]:
                    by_idx_div[key] += 1
            else:
                by_idx_low[key] += 1
                if e["has_divergence"]:
                    by_idx_low_div[key] += 1

        print(f"\n{label}序列信号（去重后，每序列段仅计1次）:")
        print(f"{'指数':<10} {'高9段':>6} {'低9段':>6} {'钝化+高9':>8} {'钝化+低9':>8}")
        print("-" * 45)
        for code in INDICES:
            name = INDEX_NAMES[code]
            print(f"{name:<10} {by_idx[name]:>6} {by_idx_low[name]:>6} "
                  f"{by_idx_div[name]:>8} {by_idx_low_div[name]:>8}")

    # 共振事件（≤30条）
    print(f"\n{'─' * 80}")
    print(f"多指数/多周期共振（≥2指数 或 多周期）: {len(resonance)} 次")
    if len(resonance) > 0:
        print(f"{'日期':<14} {'方向':>4} {'指数':>4} {'周期':>8} {'最大计':>6} {'钝+9':>5} {'指数'}")
        print("-" * 85)
        for _, r in resonance.head(30).iterrows():
            div_flag = "✓" if r["has_div"] else ""
            print(f"{r['date'].strftime('%Y-%m-%d'):<14} "
                  f"{r['direction']:>4}9 "
                  f"{int(r['n_indices']):>4}指 "
                  f"{r['periods']:>8} "
                  f"{int(r['max_count']):>6} "
                  f"{div_flag:>5} "
                  f"{r['indices'][:50]}")

    # 月线序列
    if "monthly" in results:
        mf = results["monthly"]
        print(f"\n{'─' * 80}")
        print("月线序列（最高分——大几年才一见）:")
        for code in INDICES:
            sub = mf[mf["index_code"] == code].sort_values("date")
            if sub.empty:
                continue
            name = INDEX_NAMES[code]
            h9_dates = sub[sub["turn_high_count"] >= 8]["date"].dt.strftime("%Y-%m").tolist()
            l9_dates = sub[sub["turn_low_count"] >= 8]["date"].dt.strftime("%Y-%m").tolist()
            if h9_dates:
                print(f"  {name} 月线高9: {', '.join(h9_dates[:8])}{'...' if len(h9_dates)>8 else ''}")
            if l9_dates:
                print(f"  {name} 月线低9: {', '.join(l9_dates[:8])}{'...' if len(l9_dates)>8 else ''}")

    # 保存
    out = os.path.join(DATA_DIR, "turn_sequence_events.csv")
    pd.DataFrame(events).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n→ {out}")
    out_r = os.path.join(DATA_DIR, "turn_sequence_resonance.csv")
    resonance.to_csv(out_r, index=False, encoding="utf-8-sig")
    print(f"→ {out_r}")


if __name__ == "__main__":
    daily_path = os.path.join(DATA_DIR, "daily_ma_channels.csv")
    if not os.path.exists(daily_path):
        print("请先运行 scripts/fetch_data.py")
        sys.exit(1)
    results = build_sequence_for_all(daily_path)
    report(results)
