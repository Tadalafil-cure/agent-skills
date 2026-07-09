#!/usr/bin/env python3
"""
concentration.py — 筹码集中度四级评估引擎

输入：data_package.stock.shareholder_count + top10_shareholders + quote
输出：筹码集中度四级评估表（高度控盘/中度控盘/低度控盘）

判定规则：
  指标          高度控盘        中度控盘        低度控盘
  股东户数变化   持续减少        波动不定        持续增加
  户均持股趋势   持续增加        相对稳定        持续减少
  十大股东占比   >60%           40-60%          <40%
  机构持股占比   >30%           15-30%          <15%
  换手率水平     较低(<2%)       适中(2-5%)      较高(>5%)

用法：
  python concentration.py --file /tmp/agent_d_data.json
  python concentration.py --input '<json>'
  cat data.json | python concentration.py
"""

import json
import sys
import argparse


def _trend(values: list) -> str:
    """判断趋势方向（基于最近 4 期）。"""
    if not values or len(values) < 2:
        return "数据不足"
    recent = values[-4:] if len(values) >= 4 else values
    if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
        return "持续增加"
    elif all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
        return "持续减少"
    else:
        return "波动不定"


def classify(shareholder_count: dict, top10: dict, quote: dict) -> dict:
    """筹码集中度四级评估。"""

    # ── 股东户数变化 ──
    sc_data = shareholder_count.get("data", shareholder_count)
    holder_counts = []
    avg_holdings = []
    if isinstance(sc_data, list) and sc_data:
        for r in sc_data:
            hc = r.get("股东户数") or r.get("holder_count") or r.get("shareholder_count")
            if hc:
                holder_counts.append(float(hc))
            ah = r.get("户均持股") or r.get("avg_holding") or r.get("avg_holdings")
            if ah:
                avg_holdings.append(float(ah))

    holder_trend = _trend(holder_counts) if holder_counts else "数据不足"
    avg_hold_trend = _trend(avg_holdings) if avg_holdings else "数据不足"

    # ── 十大股东占比 ──
    top10_data = top10.get("data", top10)
    top10_ratio = None
    if isinstance(top10_data, list) and top10_data:
        total = 0.0
        for r in top10_data:
            ratio = r.get("持股比例") or r.get("ratio") or r.get("share_ratio") or 0
            try:
                total += float(ratio)
            except (ValueError, TypeError):
                pass
        if total > 0:
            top10_ratio = round(total, 2)

    # ── 机构持股占比 ──
    # 从十大股东中识别机构（排除个人/国资委/控股公司等）
    inst_ratio = None
    if isinstance(top10_data, list) and top10_data:
        total = 0.0
        for r in top10_data:
            name = str(r.get("股东名称", "") or r.get("holder_name", "") or r.get("name", ""))
            ratio = r.get("持股比例") or r.get("ratio") or r.get("share_ratio") or 0
            try:
                rv = float(ratio)
            except (ValueError, TypeError):
                continue
            # 机构标志：基金/证券/保险/信托/社保/QFII/年金/资管
            is_inst = any(kw in name for kw in [
                "基金", "证券", "保险", "信托", "社保", "QFII",
                "年金", "资管", "银行", "有限合伙", "投资公司",
                "Fund", "Securities", "Insurance", "Trust",
            ])
            if is_inst:
                total += rv
        if total > 0:
            inst_ratio = round(total, 2)

    # ── 换手率 ──
    qdata = quote.get("data", quote)
    turnover = qdata.get("换手率")
    if turnover is not None:
        turnover = float(turnover)

    # ── 四级评估 ──
    def grade_hc(trend_str):
        if "减少" in str(trend_str): return "高度控盘"
        if "增加" in str(trend_str): return "低度控盘"
        return "中度控盘"

    def grade_ah(trend_str):
        if "增加" in str(trend_str): return "高度控盘"
        if "减少" in str(trend_str): return "低度控盘"
        return "中度控盘"

    def grade_top10(ratio):
        if ratio is None: return "数据不足"
        if ratio > 60: return "高度控盘"
        if ratio >= 40: return "中度控盘"
        return "低度控盘"

    def grade_inst(ratio):
        if ratio is None: return "数据不足"
        if ratio > 30: return "高度控盘"
        if ratio >= 15: return "中度控盘"
        return "低度控盘"

    def grade_turnover(t):
        if t is None: return "数据不足"
        if t < 2: return "高度控盘"
        if t <= 5: return "中度控盘"
        return "低度控盘"

    rows = [
        {"指标": "股东户数变化", "高度控盘": "持续减少", "中度控盘": "波动不定", "低度控盘": "持续增加",
         "当前值": holder_trend, "判定": grade_hc(holder_trend)},
        {"指标": "户均持股趋势", "高度控盘": "持续增加", "中度控盘": "相对稳定", "低度控盘": "持续减少",
         "当前值": avg_hold_trend, "判定": grade_ah(avg_hold_trend)},
        {"指标": "十大股东占比", "高度控盘": ">60%", "中度控盘": "40-60%", "低度控盘": "<40%",
         "当前值": f"{top10_ratio}%" if top10_ratio is not None else "数据不足", "判定": grade_top10(top10_ratio)},
        {"指标": "机构持股占比", "高度控盘": ">30%", "中度控盘": "15-30%", "低度控盘": "<15%",
         "当前值": f"{inst_ratio}%" if inst_ratio is not None else "数据不足", "判定": grade_inst(inst_ratio)},
        {"指标": "换手率水平", "高度控盘": "较低", "中度控盘": "适中", "低度控盘": "较高",
         "当前值": f"{turnover}%" if turnover is not None else "数据不足", "判定": grade_turnover(turnover)},
    ]

    # 综合判定
    grades = [r["判定"] for r in rows if r["判定"] != "数据不足"]
    if not grades:
        overall = "数据不足"
    else:
        high = grades.count("高度控盘")
        mid = grades.count("中度控盘")
        low = grades.count("低度控盘")
        if high >= 3:
            overall = "高度控盘"
        elif low >= 3:
            overall = "低度控盘"
        else:
            overall = "中度控盘"

    return {
        "table": rows,
        "overall": overall,
        "holdings_chart_data": {
            "holder_counts": holder_counts,
            "avg_holdings": avg_holdings,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="筹码集中度四级评估引擎")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    parser.add_argument("--file", type=str, help="JSON 文件路径")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
    elif args.input:
        data = json.loads(args.input)
    else:
        data = json.load(sys.stdin)

    stock = data.get("stock", data)

    result = classify(
        stock.get("shareholder_count", {}),
        stock.get("top10", stock.get("top10_shareholders", {})),
        stock.get("quote", {}),
    )
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
