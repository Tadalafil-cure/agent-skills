#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  推论信号系统 · Inference Signals v2                        ║
║  ⛔ 独立模块 · 严禁与裁决引擎混用                            ║
╚══════════════════════════════════════════════════════════════╝

定位：基于历史回测数据的经验规律，非徐小明方法论直接产物。
     与裁决引擎（verdict_v7）完全独立——不互调、不叠加、不覆盖。

使用方式：裁决引擎给操作结论（买/卖/等），推论信号给风险提示
         （历史上这种情况发生了什么）。两者并行展示，互不替代。

v2 更新（2026-07-19）：
  - S3/S4 从文档定义补全为完整检测+追踪逻辑
  - S3 追踪式检测：入震后持续追踪首高/减仓状态，退震后给出完整回顾
  - S4 追踪式检测：下行来路入震后追踪 BS 累计，BS≥2 触发试探
  - 新增 _find_current_osc_period() 统一来路判断
"""

import pandas as pd
import numpy as np
import json
import sys
import os
from datetime import datetime

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
        "type": "entry",  # 入震时触发
    },
    "S2": {
        "name": "首次偏空续跌信号",
        "desc": "regime首次转为偏空时，后续大概率继续下跌",
        "trigger": "regime首次从非偏空→偏空（单日即判，不等3天确认）",
        "confidence": "HIGH",
        "confidence_reason": "深证77次回测，续跌68次(88%)，零反亏(0%)，中位续跌-5.2%",
        "action": "🔴 偏空首日是一个可靠的辅助砍仓参考点。不砍的话中位还要亏-5.2%",
        "type": "exit",  # 退震时触发
    },
    "S3": {
        "name": "入震减仓策略（分市场 · 上行来路）",
        "desc": "上行来路进入震荡后，不同市场的首高反弹特征不同，最佳退出策略不同。追踪整个震荡周期。",
        "trigger": "regime从偏多/上行趋势→震荡（日线确认），此后持续追踪至退震",
        "confidence": "HIGH",
        "confidence_reason": "四指数全量回测：双创等首高优于T+1全砍(69-80%)，上证深证T+1全砍即可",
        "type": "tracking",  # 追踪式：入震后持续追踪
        "strategy": {
            "双创(创业板+科创50)": "入震→等首高(≤5天)→清仓。T+1先减25%防踏空，5天无首高强制清。",
            "上证/深证": "入震→T+1减50%。首高反弹小(中位+1.1-1.3%)，不值得等。",
        },
    },
    "S4": {
        "name": "下行来路入震+BS≥2试探",
        "desc": "下行来路进入震荡后，追踪底部结构(BS)累计。BS≥2=试探入场，BS=1=陷阱不进场。",
        "trigger": "regime从偏空/下行趋势→震荡，此后追踪 BS 累计至退震",
        "confidence": "HIGH",
        "confidence_reason": "四指数全量回测：双创BS≥2=100%走强(中位+4-5%)，BS=1=38%走强(陷阱)",
        "type": "tracking",  # 追踪式：入震后持续追踪
        "strategy": {
            "双创(创业板+科创50)": "BS≥2→试探≤25%仓位，8-10天确认走高。BS=1→不入场(走强率仅38%)。",
            "深证": "BS≥2→试探≤15%仓位，14天确认。BS=1→不入场。",
            "上证": "BS≥2也不进场——中位仅+1.4%，不值得。",
        },
    },
}


# ── 回测引擎 ────────────────────────────────────────────

def _load_data(path="data/verdict_v7.csv"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, "..", path)
    v = pd.read_csv(full_path)
    v = v.sort_values("date")
    v["date"] = pd.to_datetime(v["date"])
    return v


def _find_current_osc_period(v):
    """
    从最新数据往前追溯，找到最近一个震荡期的入震日和来路。
    返回: {
        "in_oscillation": bool,       # 当前是否在震荡中
        "entry_date": str,            # 入震日期
        "exit_date": str | None,      # 退震日期（已退震时）
        "origin": "上行" | "下行" | "不明",  # 来路
        "days_in_osc": int,           # 已震荡天数
        "entry_chop": float,          # 入震时 CHOP
    }
    """
    # 找最新的非交易日（可能有重复行）
    latest = v.iloc[-1]
    prev_row = v.iloc[-2]
    if latest["close_sz"] == prev_row["close_sz"] and latest["date"] != prev_row["date"]:
        latest = prev_row
        prev_row = v.iloc[-3]

    curr_regime = latest["regime_sz"]
    date_str = str(latest["date"])[:10]

    # 如果当前不在震荡中，找最近一次震荡的入口
    if curr_regime != "震荡":
        # 向前找最近一次从非震荡→震荡的切换
        for i in range(len(v) - 2, 0, -1):
            if v.iloc[i]["regime_sz"] == "震荡" and v.iloc[i - 1]["regime_sz"] != "震荡":
                entry_idx = i
                prev_regime = v.iloc[i - 1]["regime_sz"]
                # 找来路
                origin = "不明"
                if prev_regime in ["上行趋势", "偏多"]:
                    origin = "上行"
                elif prev_regime in ["下行趋势", "偏空"]:
                    origin = "下行"

                # 找退震日
                exit_idx = None
                for j in range(i + 1, len(v)):
                    if v.iloc[j]["regime_sz"] != "震荡":
                        exit_idx = j
                        break

                return {
                    "in_oscillation": False,
                    "entry_date": str(v.iloc[entry_idx]["date"])[:10],
                    "exit_date": str(v.iloc[exit_idx]["date"])[:10] if exit_idx else None,
                    "origin": origin,
                    "days_in_osc": (exit_idx - entry_idx) if exit_idx else (len(v) - entry_idx),
                    "entry_chop": float(v.iloc[entry_idx]["chop_sz"]),
                }
        return None  # 没有找到震荡期

    # 当前在震荡中
    for i in range(len(v) - 2, 0, -1):
        if v.iloc[i]["regime_sz"] != "震荡" and v.iloc[i - 1]["regime_sz"] == "震荡":
            continue
        if v.iloc[i]["regime_sz"] == "震荡" and v.iloc[i - 1]["regime_sz"] != "震荡":
            entry_idx = i
            prev_regime = v.iloc[i - 1]["regime_sz"]
            origin = "不明"
            if prev_regime in ["上行趋势", "偏多"]:
                origin = "上行"
            elif prev_regime in ["下行趋势", "偏空"]:
                origin = "下行"
            return {
                "in_oscillation": True,
                "entry_date": str(v.iloc[entry_idx]["date"])[:10],
                "exit_date": None,
                "origin": origin,
                "days_in_osc": len(v) - entry_idx - 1,  # 减去最后可能的非交易日
                "entry_chop": float(v.iloc[entry_idx]["chop_sz"]),
            }

    return None


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
        results.append({
            "entry_date": str(seg.iloc[0]["date"])[:10],
            "entry_chop": chop,
            "first_high": fp,
            "trough": seg["close_sz"].min(),
            "dd_pct": round(dd, 1),
            "deep": dd < -8,
            "osc_days": len(seg),
        })
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
        results.append({
            "entry_date": str(e["date"])[:10],
            "entry_close": e["close_sz"],
            "trough": trough,
            "dd_pct": round(dd, 1),
            "continued_drop": dd < 0,
        })
    return results


def _backtest_s3(v):
    """S3: 上行来路入震 → 追踪首高与减仓时机"""
    prev = v["regime_sz"].shift(1)
    in_osc = (prev != "震荡") & (v["regime_sz"] == "震荡")

    results = []
    for entry_idx in v[in_osc].index:
        pre = v.loc[entry_idx - 1, "regime_sz"] if entry_idx > 0 else ""
        if pre not in ["上行趋势", "偏多"]:
            continue

        # 找震荡段结束
        i = entry_idx
        while i < len(v) - 1 and v.loc[i, "regime_sz"] == "震荡":
            i += 1
        seg = v.iloc[entry_idx : i + 1]

        # 找四指数的首高
        entry_dates = {}
        for idx_col, close_col in [("sh", "close_sh"), ("sz", "close_sz"),
                                     ("cyb", "close_cyb"), ("kc", "close_kc")]:
            if close_col not in seg.columns:
                continue
            first10 = seg.iloc[:10][close_col].dropna()
            if len(first10) == 0:
                entry_dates[idx_col] = {"first_high_date": None, "days_to_high": None, "within_5d": False}
                continue
            # 取 first10 在原 seg 中的位置
            max_val = first10.max()
            max_date = seg.loc[seg[close_col] == max_val, "date"]
            if len(max_date) == 0:
                entry_dates[idx_col] = {"first_high_date": None, "days_to_high": None, "within_5d": False}
                continue
            first_high_date = str(max_date.iloc[0])[:10]
            days_to_high = (max_date.iloc[0] - seg.iloc[0]["date"]).days
            entry_dates[idx_col] = {
                "first_high_date": first_high_date,
                "days_to_high": days_to_high,
                "within_5d": days_to_high <= 5,
            }

        results.append({
            "entry_date": str(seg.iloc[0]["date"])[:10],
            "osc_days": len(seg),
            "first_highs": entry_dates,
        })
    return results


def _backtest_s4(v):
    """S4: 下行来路入震 → 追踪 BS 累计与试探信号"""
    prev = v["regime_sz"].shift(1)
    in_osc = (prev != "震荡") & (v["regime_sz"] == "震荡")

    results = []
    for entry_idx in v[in_osc].index:
        pre = v.loc[entry_idx - 1, "regime_sz"] if entry_idx > 0 else ""
        if pre not in ["下行趋势", "偏空"]:
            continue

        i = entry_idx
        while i < len(v) - 1 and v.loc[i, "regime_sz"] == "震荡":
            i += 1
        seg = v.iloc[entry_idx : i + 1]

        # 追踪四指数的 BS 累计
        bs_tracking = {}
        for idx_col, bs_col in [("sh", "bs_sh"), ("sz", "bs_sz"),
                                  ("cyb", "bs_cyb"), ("kc", "bs_kc")]:
            if bs_col not in seg.columns:
                continue
            bs_cum = seg[bs_col].cumsum().max()
            bs_dates = seg[seg[bs_col] == 1]["date"].tolist()
            bs_dates_str = [str(d)[:10] for d in bs_dates]

            # 判断是否触发 S4
            if bs_cum >= 2:
                action = "试探" if idx_col != "sh" else "不进场(上证中位仅+1.4%)"
            elif bs_cum == 1:
                action = "不入场(BS=1陷阱,走强率38%)"
            else:
                action = "不判断(BS=0,抛硬币)"

            bs_tracking[idx_col] = {
                "bs_total": int(bs_cum),
                "bs_dates": bs_dates_str,
                "action": action,
            }

        results.append({
            "entry_date": str(seg.iloc[0]["date"])[:10],
            "osc_days": len(seg),
            "bs_tracking": bs_tracking,
        })
    return results


# ── 当前触发检测 ────────────────────────────────────────

def check_signals(v):
    """检测最新交易日是否触发推论信号（含 S3/S4 追踪式检测）"""
    # 取最新有效行
    latest = v.iloc[-1]
    prev_row = v.iloc[-2]
    if latest["close_sz"] == prev_row["close_sz"] and latest["date"] != prev_row["date"]:
        latest = prev_row
        prev_row = v.iloc[-3]

    date_str = str(latest["date"])[:10]
    curr_regime = latest["regime_sz"]
    prev_regime = prev_row["regime_sz"]

    triggered = []
    details = {}

    # ── S1: 上行来路 + 刚入震 + CHOP>60 ──
    just_entered_osc = (prev_regime != "震荡" and curr_regime == "震荡")
    if just_entered_osc and prev_regime in ["上行趋势", "偏多"] and latest["chop_sz"] > 60:
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

    # ── S2: 首次偏空 ──
    just_entered_pk = (prev_regime != "偏空" and curr_regime == "偏空")
    if just_entered_pk:
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

    # ── S3: 上行来路入震（追踪式）──
    # 触发条件：当前在震荡中且来路=上行（入震日触发），或刚退震且来路=上行（退震日回顾）
    osc = _find_current_osc_period(v)
    if osc and osc["origin"] == "上行":
        triggered.append("S3")
        backtest = _backtest_s3(v)

        # 找当前震荡段的数据
        current_entry = None
        for bt in backtest:
            if bt["entry_date"] == osc["entry_date"]:
                current_entry = bt
                break

        s3_detail = {
            "origin": "上行",
            "entry_date": osc["entry_date"],
            "days_in_osc": osc["days_in_osc"],
            "entry_chop": osc["entry_chop"],
            "status": "已退震" if not osc["in_oscillation"] else "震荡中",
        }
        if not osc["in_oscillation"]:
            s3_detail["exit_date"] = osc["exit_date"]

        if current_entry:
            s3_detail["first_highs"] = current_entry["first_highs"]

        # 当前策略建议
        s3_detail["strategy"] = SIGNALS["S3"]["strategy"]

        # 全量回测统计
        total_cases = len(backtest)
        if total_cases > 0:
            # 双创等首高命中率
            cyb_within5 = sum(1 for b in backtest
                            if "cyb" in b.get("first_highs", {})
                            and b["first_highs"]["cyb"].get("within_5d"))
            kc_within5 = sum(1 for b in backtest
                           if "kc" in b.get("first_highs", {})
                           and b["first_highs"]["kc"].get("within_5d"))
            s3_detail["backtest_summary"] = {
                "total_cases": total_cases,
                "cyb_first_high_within_5d": f"{cyb_within5}/{total_cases}",
                "kc_first_high_within_5d": f"{kc_within5}/{total_cases}",
            }

        details["S3"] = s3_detail

    # ── S4: 下行来路入震 + BS 追踪（追踪式）──
    if osc and osc["origin"] == "下行":
        backtest = _backtest_s4(v)

        # 找当前震荡段
        current_entry = None
        for bt in backtest:
            if bt["entry_date"] == osc["entry_date"]:
                current_entry = bt
                break

        # 检查是否有指数 BS≥2
        bs_triggered = False
        if current_entry:
            for idx_key, bs_info in current_entry.get("bs_tracking", {}).items():
                if bs_info["bs_total"] >= 2 and bs_info["action"] not in ["不进场(上证中位仅+1.4%)", ""]:
                    bs_triggered = True
                    break

        if bs_triggered or (osc["days_in_osc"] > 10):
            # 震荡超过10天或已触发→报告S4
            triggered.append("S4")
            s4_detail = {
                "origin": "下行",
                "entry_date": osc["entry_date"],
                "days_in_osc": osc["days_in_osc"],
                "status": "已退震" if not osc["in_oscillation"] else "震荡中",
            }
            if not osc["in_oscillation"]:
                s4_detail["exit_date"] = osc["exit_date"]

            if current_entry:
                s4_detail["bs_tracking"] = current_entry["bs_tracking"]

            s4_detail["strategy"] = SIGNALS["S4"]["strategy"]

            # 全量回测
            total_cases = len(backtest)
            if total_cases > 0:
                sz_bs2 = sum(1 for b in backtest
                           if "sz" in b.get("bs_tracking", {})
                           and b["bs_tracking"]["sz"]["bs_total"] >= 2)
                cyb_bs2 = sum(1 for b in backtest
                            if "cyb" in b.get("bs_tracking", {})
                            and b["bs_tracking"]["cyb"]["bs_total"] >= 2)
                kc_bs2 = sum(1 for b in backtest
                           if "kc" in b.get("bs_tracking", {})
                           and b["bs_tracking"]["kc"]["bs_total"] >= 2)
                s4_detail["backtest_summary"] = {
                    "total_cases": total_cases,
                    "sz_bs_ge2": f"{sz_bs2}/{total_cases}",
                    "cyb_bs_ge2": f"{cyb_bs2}/{total_cases}",
                    "kc_bs_ge2": f"{kc_bs2}/{total_cases}",
                }

            details["S4"] = s4_detail

    return date_str, triggered, details, osc


# ── CLI ──────────────────────────────────────────────────

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "..", "data", "verdict_v7.csv")

    v = _load_data(data_path)
    date_str, triggered, details, osc = check_signals(v)

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

    # 震荡来路摘要
    if osc:
        output["oscillation_context"] = {
            "in_oscillation": osc["in_oscillation"],
            "entry_date": osc["entry_date"],
            "origin": osc["origin"],
            "days_in_osc": osc["days_in_osc"],
        }
        if not osc["in_oscillation"]:
            output["oscillation_context"]["exit_date"] = osc["exit_date"]

    # 全部信号定义
    output["_all_signals"] = {
        sid: {
            "name": s["name"],
            "confidence": s["confidence"],
            "trigger": s["trigger"],
            "type": s.get("type", "single"),
        }
        for sid, s in SIGNALS.items()
    }

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
