#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  推论信号系统 · Inference Signals                           ║
║  ⛔ 独立模块 · 严禁与裁决引擎混用                            ║
╚══════════════════════════════════════════════════════════════╝

定位：基于历史回测数据的经验规律，非徐小明方法论直接产物。
     与裁决引擎（verdict_v7）完全独立——不互调、不叠加、不覆盖。

使用方式：裁决引擎给操作结论（买/卖/等），推论信号给风险提示
         （历史上这种情况发生了什么）。两者并行展示，互不替代。

信号来源：2026-07-17 session 全量回测分析
数据文件：data/verdict_v7.csv
"""

import pandas as pd
import numpy as np
import json
import sys
from datetime import datetime

# ⛔ 原则声明 · 写入每个输出
_DISCLAIMER = (
    "⛔ 推论信号 ≠ 裁决信号。"
    "裁决管「按规则该做什么」，推论管「历史上类似情况发生过什么」。"
    "推论不修改裁决、不覆盖裁决、不与裁决叠加。"
)

# ── 信号定义 ────────────────────────────────────────────

SIGNALS = {
    "S1": {
        "name": "入震CHOP>60深跌预警",
        "desc": "上行来路进入震荡时，若CHOP已>60，历史上震荡首高后深跌(>8%)概率极高",
        "trigger": "regime从偏多/上行趋势→震荡，且入震当日CHOP>60",
        "confidence": "LOW",
        "confidence_reason": "仅4次历史样本(3/4命中)，样本量不足，需持续积累",
        "action": "⚠️ 注意首高后的深跌风险，历史最浅跌7.7%，最深跌14.5%",
    },
    "S2": {
        "name": "首次偏空续跌信号",
        "desc": "regime首次转为偏空时，后续大概率继续下跌",
        "trigger": "regime首次从非偏空→偏空（单日即判，不等3天确认）",
        "confidence": "HIGH",
        "confidence_reason": "深证77次回测，续跌68次(88%)，零反亏(0%)，中位续跌-5.2%",
        "action": "🔴 偏空首日是一个可靠的辅助砍仓参考点。不砍的话中位还要亏-5.2%",
    },
    "S3": {
        "name": "入震减仓策略（分市场）",
        "desc": "上行来路进入震荡后，不同市场的首高反弹特征不同，最佳退出策略不同",
        "trigger": "regime从偏多/上行趋势→震荡（日线确认，实操为T+1执行）",
        "confidence": "HIGH",
        "confidence_reason": "四指数全量回测：双创等首高优于T+1全砍(69-80%)，上证深证T+1全砍即可",
        "action_by_index": {
            "双创(创业板+科创50)": "入震→T+1减25%→等首高(10天内)→清仓。首高概率85-93%，等首高优于T+1全砍69-80%",
            "上证/深证": "入震→T+1全砍。首高反弹小(中位+1.1-1.3%)，不值得等",
        },
        "backtest_summary": "创业板26段:等首高vs死扛100%优于(+4.6%); 科创50:15段100%优于(+4.5%); 深证:等首高仅39%优于T+1全砍",
    },
}


# ── 回测引擎 ────────────────────────────────────────────

def _load_data(path="data/verdict_v7.csv"):
    v = pd.read_csv(path)
    v = v.sort_values("date")
    v["date"] = pd.to_datetime(v["date"])
    return v


def _backtest_s1(v):
    """S1: 上行来路 + 入震CHOP>60 → 首高后深跌"""
    prev = v["regime_sz"].shift(1)
    in_osc = (prev != "震荡") & (v["regime_sz"] == "震荡")

    results = []
    for entry_idx in v[in_osc].index:
        pre = v.loc[entry_idx - 1, "regime_sz"] if entry_idx > 0 else ""
        if pre not in ["上行趋势", "偏多"]:
            continue
        chop = v.loc[entry_idx, "chop_sz"]
        if chop < 60:
            continue
        i = entry_idx
        while i < len(v) - 1 and v.loc[i, "regime_sz"] == "震荡":
            i += 1
        seg = v.iloc[entry_idx : i + 1]
        if len(seg) < 5:
            continue
        fp = seg.iloc[:10]["close_sz"].max()
        dd = (seg["close_sz"].min() - fp) / fp * 100
        results.append(
            {
                "entry_date": str(seg.iloc[0]["date"])[:10],
                "entry_chop": chop,
                "first_high": fp,
                "trough": seg["close_sz"].min(),
                "dd_pct": round(dd, 1),
                "deep": dd < -8,
                "osc_days": len(seg),
            }
        )
    return results


def _backtest_s2(v):
    """S2: 首次偏空 → 后续续跌"""
    prev = v["regime_sz"].shift(1)
    first_pk = (prev != "偏空") & (v["regime_sz"] == "偏空")

    results = []
    for _, e in v[first_pk].iterrows():
        future = v[
            (v["date"] >= e["date"])
            & (v["date"] <= e["date"] + pd.Timedelta(days=120))
        ]
        if len(future) == 0:
            continue
        trough = future["close_sz"].min()
        dd = (trough - e["close_sz"]) / e["close_sz"] * 100
        results.append(
            {
                "entry_date": str(e["date"])[:10],
                "entry_close": e["close_sz"],
                "trough": trough,
                "dd_pct": round(dd, 1),
                "continued_drop": dd < 0,
            }
        )
    return results


# ── 当前触发检测 ────────────────────────────────────────

def check_signals(v):
    """检测最新交易日是否触发推论信号"""
    # 最新两行：最后一行可能是非交易日（数据与前一交易日相同），取倒数第二行
    latest = v.iloc[-1]
    prev_row = v.iloc[-2]

    # 如果最后一行 close 与前一行相同，说明是非交易日重复，退回前一天
    if latest["close_sz"] == prev_row["close_sz"] and latest["date"] != prev_row["date"]:
        latest = prev_row
        prev_row = v.iloc[-3]

    date_str = str(latest["date"])[:10]
    curr_regime = latest["regime_sz"]
    prev_regime = prev_row["regime_sz"]

    triggered = []
    details = {}
    # 检测是否"刚入震"（前一天非震荡，当天震荡）
    if prev_regime != "震荡" and curr_regime == "震荡":
        if prev_regime in ["上行趋势", "偏多"] and latest["chop_sz"] > 60:
            results = _backtest_s1(v)
            triggered.append("S1")
            deep = [r for r in results if r["deep"]]
            details["S1"] = {
                "total": len(results),
                "deep_hits": len(deep),
                "hit_rate": f"{len(deep)}/{len(results)}",
                "worst_dd": min(r["dd_pct"] for r in results) if results else None,
                "current_chop": float(latest["chop_sz"]),
            }

    # S2: 首次偏空
    if prev_regime != "偏空" and curr_regime == "偏空":
        results = _backtest_s2(v)
        triggered.append("S2")
        dds = [r["dd_pct"] for r in results]
        continued = [r for r in results if r["continued_drop"]]
        details["S2"] = {
            "total": len(results),
            "continued": len(continued),
            "hit_rate": f"{len(continued)}/{len(results)} ({len(continued)/len(results)*100:.0f}%)",
            "median_dd": round(np.median(dds), 1),
            "mean_dd": round(np.mean(dds), 1),
            "worst_dd": round(min(dds), 1),
            "reversed": sum(1 for d in dds if d >= 0),
            "current_close": float(latest["close_sz"]),
            "projected_median": round(float(latest["close_sz"]) * (1 + np.median(dds) / 100), 0),
        }

    return date_str, triggered, details


# ── CLI ──────────────────────────────────────────────────

def main():
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "..", "data", "verdict_v7.csv")

    v = _load_data(data_path)
    date_str, triggered, details = check_signals(v)

    output = {
        "disclaimer": _DISCLAIMER,
        "date": date_str,
        "source": "推论信号 · 独立于裁决引擎 · 严禁混用",
        "note": "以下信号基于历史回测，非徐小明方法论直接产物。不修改、不覆盖、不叠加裁决。",
        "triggered": triggered,
        "signals": {},
    }

    for sid in triggered:
        s = SIGNALS[sid].copy()
        s["backtest"] = details[sid]
        output["signals"][sid] = s

    # Also include full historical stats for all signals
    output["_all_signals"] = {
        sid: {"name": s["name"], "confidence": s["confidence"], "trigger": s["trigger"]}
        for sid, s in SIGNALS.items()
    }

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
