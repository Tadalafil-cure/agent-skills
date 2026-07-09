#!/usr/bin/env python3
"""
bayesian_update.py — 贝叶斯概率更新引擎 v2.0

将 B3 的「先验→新证据→后验」三段式贝叶斯更新机械化为确定性计算。

核心设计：证据强度不是单点 LR，而是一个区间 [LR_low, LR_high]。
→ 输出后验区间而非单点估计 → 不确定性透明暴露。

输入: JSON (stdin / --file / --input)
输出: 结构化更新链 + 敏感性分析 + 后验区间

用法:
  python bayesian_update.py --file bayesian_input.json
  python bayesian_update.py --input '<json>'
  cat input.json | python bayesian_update.py
"""

import json
import sys
import argparse
import math


# ── 似然比区间映射表 ──────────────────────────────────────
# 每条证据的强度映射为一个 LR 区间，而非单点。
# [LR_low, LR_high] 代表保守→激进两种合理校准。

STRENGTH_RANGE_MAP = {
    "强正向":   (3.0, 8.0),   # 保守: LR=3(60%→75%), 激进: LR=8(60%→92%)
    "中正向":   (1.8, 4.0),   # 保守: LR=1.8(60%→73%), 激进: LR=4(60%→86%)
    "弱正向":   (1.2, 2.0),   # 保守: LR=1.2(60%→64%), 激进: LR=2(60%→75%)
    "弱负向":   (0.50, 0.83), # 1/2.0 ~ 1/1.2
    "中负向":   (0.25, 0.56), # 1/4.0 ~ 1/1.8
    "强负向":   (0.125, 0.33),# 1/8.0 ~ 1/3.0
    "中性":     (0.90, 1.10),
}

# 默认取区间中点作为"基准"估计，用于单点输出
DEFAULT_POINT = "mid"


def bayesian_update(prior: float, likelihood_ratio: float) -> float:
    """单步贝叶斯更新：P(H|E) = P(H) × LR / (1 - P(H) + P(H) × LR)"""
    if prior <= 0 or prior >= 1:
        raise ValueError(f"先验概率必须在 (0, 1) 之间，收到: {prior}")
    if likelihood_ratio <= 0:
        raise ValueError(f"似然比必须 > 0，收到: {likelihood_ratio}")
    return prior * likelihood_ratio / (1 - prior + prior * likelihood_ratio)


def full_update_chain(prior: float, lr_list: list) -> list:
    """用一系列 LR 逐步更新，返回每步的 (prior, posterior, lr)"""
    steps = []
    current = prior
    for lr in lr_list:
        new_p = bayesian_update(current, lr)
        steps.append((current, new_p, lr))
        current = new_p
    return steps


def interval_to_judgment(posterior_low: float, posterior_high: float) -> str:
    """将后验区间映射为裁决可用的定性判断"""
    spread = posterior_high - posterior_low

    # 整个区间在 0.5 以上 → 倾向支持
    if posterior_low > 0.65:
        base = "强烈支持"
    elif posterior_low > 0.55:
        base = "倾向支持"
    elif posterior_high < 0.35:
        base = "强烈反对"
    elif posterior_high < 0.45:
        base = "倾向反对"
    elif posterior_low < 0.40 and posterior_high > 0.60:
        base = "高度不确定（区间跨 0.5 且宽）"
    else:
        base = "中性偏不确定"

    if spread > 0.25:
        qual = "，参数敏感性高——建议审慎使用"
    elif spread > 0.12:
        qual = "，参数敏感性中等"
    else:
        qual = "，参数稳定"

    return base + qual


def main():
    parser = argparse.ArgumentParser(description="贝叶斯概率更新引擎 v2.0")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    parser.add_argument("--file", type=str, help="JSON 文件路径")
    parser.add_argument("--point", type=str, default="mid",
                        choices=["mid", "low", "high"],
                        help="单点模式: mid=区间中点, low=保守, high=激进")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
    elif args.input:
        data = json.loads(args.input)
    else:
        data = json.load(sys.stdin)

    prior = data.get("prior")
    hypothesis = data.get("hypothesis", "未命名假设")
    evidences = data.get("evidences", [])

    if prior is None:
        print(json.dumps({"error": "缺少 'prior' 字段（先验概率）"}, ensure_ascii=False))
        sys.exit(1)

    # ── 提取每条证据的 LR 区间 ──
    lr_ranges = []  # [(lr_low, lr_mid, lr_high), ...]
    evidence_labels = []

    for ev in evidences:
        desc = ev.get("description", "未命名证据")
        strength = ev.get("strength", "弱")
        direction = ev.get("direction", "中性")

        # 支持直接指定区间
        if "lr_low" in ev and "lr_high" in ev:
            lr_low = float(ev["lr_low"])
            lr_high = float(ev["lr_high"])
            lr_mid = (lr_low + lr_high) / 2
        else:
            key = f"{strength}{direction}"
            lr_low, lr_high = STRENGTH_RANGE_MAP.get(key, (0.90, 1.10))
            lr_mid = (lr_low + lr_high) / 2

        # 也支持单点 LR（向后兼容）
        if "lr" in ev:
            lr_mid = float(ev["lr"])
            lr_low = lr_mid
            lr_high = lr_mid

        lr_ranges.append((lr_low, lr_mid, lr_high))
        evidence_labels.append(desc)

    # ── 三条轨迹：保守 / 基准 / 激进 ──
    lr_lows = [r[0] for r in lr_ranges]
    lr_mids = [r[1] for r in lr_ranges]
    lr_highs = [r[2] for r in lr_ranges]

    steps_low = full_update_chain(prior, lr_lows)
    steps_mid = full_update_chain(prior, lr_mids)
    steps_high = full_update_chain(prior, lr_highs)

    posterior_low = steps_low[-1][1] if steps_low else prior
    posterior_mid = steps_mid[-1][1] if steps_mid else prior
    posterior_high = steps_high[-1][1] if steps_high else prior

    # ── 逐步轨迹 ──
    step_trace = []
    for i, (label, r) in enumerate(zip(evidence_labels, lr_ranges)):
        lr_l, lr_m, lr_h = r
        step_trace.append({
            "step": i + 1,
            "evidence": label,
            "lr_range": [round(lr_l, 3), round(lr_h, 3)],
            "lr_mid": round(lr_m, 3),
            "posterior_low": round(steps_low[i][1], 4),
            "posterior_mid": round(steps_mid[i][1], 4),
            "posterior_high": round(steps_high[i][1], 4),
        })

    # ── 敏感性：先验 ±0.10 ──
    def sens(p, lr_list):
        steps = full_update_chain(p, lr_list)
        return steps[-1][1] if steps else p

    prior_up = min(prior + 0.10, 0.99)
    prior_down = max(prior - 0.10, 0.01)

    sens_result = {
        "prior_range": [round(prior_down, 2), round(prior_up, 2)],
        "posterior_low_track": {
            "at_prior_low": round(sens(prior_down, lr_lows), 4),
            "at_prior_high": round(sens(prior_up, lr_lows), 4),
        },
        "posterior_mid_track": {
            "at_prior_low": round(sens(prior_down, lr_mids), 4),
            "at_prior_high": round(sens(prior_up, lr_mids), 4),
        },
        "posterior_high_track": {
            "at_prior_low": round(sens(prior_down, lr_highs), 4),
            "at_prior_high": round(sens(prior_up, lr_highs), 4),
        },
    }

    # ── 裁决建议 ──
    judgment = interval_to_judgment(posterior_low, posterior_high)

    # ── 确信度 ──
    spread = posterior_high - posterior_low
    if spread > 0.25:
        confidence_stars = 2
    elif spread > 0.15:
        confidence_stars = 3
    elif spread > 0.08:
        confidence_stars = 4
    else:
        confidence_stars = 5

    result = {
        "hypothesis": hypothesis,
        "prior": round(prior, 4),
        "posterior": {
            "conservative": round(posterior_low, 4),
            "baseline": round(posterior_mid, 4),
            "aggressive": round(posterior_high, 4),
            "spread": round(posterior_high - posterior_low, 4),
        },
        "judgment": judgment,
        "confidence_stars": confidence_stars,
        "steps": step_trace,
        "sensitivity": sens_result,
        "note": (
            "LR区间: 强(3-8) 中(1.8-4) 弱(1.2-2)。"
            "保守=区间下限, 基准=中点, 激进=上限。"
            "区间宽度反映证据强度的主观不确定性——"
            "若 analyst 有充分理由缩小区间，可用 lr_low/lr_high 直接指定。"
        ),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
