#!/usr/bin/env python3
"""
signal.py — 三信号交叉决策矩阵

输入：scorer.py full 模式输出
输出：决策类型 + 置信度 + 仓位 + 止损 + 目标

用法：
  python signal.py --input '<json>'
"""

import json
import sys
import argparse


def cross_decision(scores: dict) -> dict:
    """三信号交叉决策。"""
    timing = scores.get("technical_timing", 0)         # -10 ~ +10
    fundamental = scores.get("fundamental_quality", 0)  # 0 ~ 25
    auto = scores.get("auto_score", 0)                  # 0 ~ 100

    # ── 决策矩阵 ──
    if timing >= 5 and fundamental >= 12:
        decision = "最佳买点"
        confidence = min(95, auto + 10)
        reason = "技术面强势 + 基本面扎实，共振买点"
        position_pct = 20
    elif timing >= 3 and fundamental >= 8:
        decision = "接近买点"
        confidence = auto
        reason = "技术面向好但基本面未完全确认"
        position_pct = 15
    elif timing >= 1 and fundamental >= 5:
        decision = "启动信号"
        confidence = auto - 5
        reason = "技术面初步转好，关注基本面确认"
        position_pct = 10
    elif timing >= 5 and fundamental < 8:
        decision = "追高风险"
        confidence = auto - 15
        reason = "技术面强势但基本面支撑不足，追高风险"
        position_pct = 5
    elif timing <= -5:
        decision = "等待"
        confidence = max(10, auto - 20)
        reason = "技术面严重偏空，建议等待"
        position_pct = 0
    elif timing <= -3 and fundamental <= 5:
        decision = "超跌关注"
        confidence = auto - 10
        reason = "技术面和基本面均偏弱，关注超跌反弹机会"
        position_pct = 0
    else:
        decision = "等待"
        confidence = max(20, auto - 10)
        reason = "信号不明确，建议观望"
        position_pct = 0

    confidence = max(0, min(100, int(confidence)))

    # ── 止损/目标（从输入中提取价格信息） ──
    price_data = scores.get("price", {})
    latest_price = price_data.get("latest", 0) or scores.get("latest_price", 0)

    # 兜底：从 K 线数据直接读现价（不依赖 scorer 传入）
    kline = scores.get("_kline", [])
    if not latest_price and kline:
        # K 线可能升序或降序——取日期最新的那条
        def _parse_date(d):
            return d.get("日期", d.get("date", ""))
        newest = max(kline, key=lambda r: _parse_date(r))
        latest_price = newest.get("收盘", 0) or newest.get("close", 0)

    stop_loss = None
    target_base = None
    target_optimistic = None
    target_conservative = None

    if latest_price:
        # ATR 止损（如可用）
        atr_val = scores.get("atr", {}).get("value", 0) or price_data.get("atr_value", 0)
        if atr_val:
            stop_loss = round(latest_price - atr_val * 2, 2)
        else:
            # 固定比例止损
            stop_loss = round(latest_price * 0.92, 2)

        # 目标价（基于近期波幅，与之前逻辑一致）
        change_20d = price_data.get("change_pct_20d", 0) or 0
        # 兜底：从 K 线自算 20 日涨跌幅
        if not change_20d and len(kline) >= 21:
            # K 线可能升序或降序，取日期倒数第 21 的新条目
            sorted_k = sorted(kline, key=lambda r: _parse_date(r))
            p20 = sorted_k[-21].get("收盘", 0) or sorted_k[-21].get("close", 0)
            if p20:
                change_20d = (latest_price / p20 - 1) * 100
        upside = max(5, min(30, abs(change_20d)))
        target_conservative = round(latest_price * (1 + upside / 200), 2)
        target_base = round(latest_price * (1 + upside / 100), 2)
        target_optimistic = round(latest_price * (1 + upside / 67), 2)

    return {
        "decision": decision,
        "confidence": confidence,
        "reason": reason,
        "suggested_position_pct": position_pct,
        "stop_loss": stop_loss,
        "target_optimistic": target_optimistic,
        "target_base": target_base,
        "target_conservative": target_conservative,
    }


def main():
    parser = argparse.ArgumentParser(description="三信号交叉决策")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    args = parser.parse_args()

    data = json.loads(args.input) if args.input else json.load(sys.stdin)
    result = cross_decision(data)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
