#!/usr/bin/env python3
"""
volume_classifier.py — 换手率分档引擎 v2.0

输入：data_package.stock.quote (单日模式) 或 K线 JSON 数组 (历史模式)
输出：换手率分档 + 盘子大小判定 + 近5/10/20日均值与分位

用法：
  # 单日模式（向后兼容）
  python volume_classifier.py --file /tmp/agent_c1_data.json
  python volume_classifier.py --input '<json>'
  cat data.json | python volume_classifier.py

  # 历史模式（深度分析）
  python volume_classifier.py --mode kline --file /tmp/daily_kline.json
  cat kline.json | python volume_classifier.py --mode kline
"""

import json
import sys
import argparse
import statistics


def classify(turnover_pct: float, float_mcap: float) -> dict:
    """换手率分档，按盘子大小修正。

    大盘股(流通市值>1000亿): <1%冷清, 1-3%正常, 3-5%活跃, >5%过热
    中小盘(流通市值<200亿): <1%冷清, 1-3%正常, 3-7%活跃, 7-15%高度活跃, >15%游资接力
    中盘股(200-1000亿): 取大盘和中小盘的中位数阈值
    """
    if float_mcap is None or float_mcap == 0:
        cap_label = "未知"
        thresholds = [(1, "冷清"), (3, "正常"), (7, "活跃"), (15, "高度活跃"), (float('inf'), "游资接力")]
    elif float_mcap > 1000_0000_0000:  # >1000亿
        cap_label = "大盘"
        thresholds = [(1, "冷清"), (3, "正常"), (5, "活跃"), (float('inf'), "过热")]
    elif float_mcap < 200_0000_0000:  # <200亿
        cap_label = "中小盘"
        thresholds = [(1, "冷清"), (3, "正常"), (7, "活跃"), (15, "高度活跃"), (float('inf'), "游资接力")]
    else:
        cap_label = "中盘"
        thresholds = [(1, "冷清"), (3, "正常"), (6, "活跃"), (10, "高度活跃"), (float('inf'), "游资接力")]

    grade = "未知"
    for limit, label in thresholds:
        if turnover_pct < limit:
            grade = label
            break

    return {
        "turnover_pct": round(turnover_pct, 2),
        "float_mcap": float_mcap,
        "cap_label": cap_label,
        "grade": grade,
    }


def classify_kline(kline_data: list, float_mcap: float) -> dict:
    """历史模式：基于完整 K 线序列分析换手率趋势。

    kline_data: K线列表，按日期升序排列，每条含 {"日期": "YYYY-MM-DD", "换手率": float}
    返回：当日分档 + 近5/10/20日均值 + 标准差 + 分位 + 趋势判断
    """
    # 提取有换手率的日K → 统一转为升序（旧→新）
    turnover_series = []
    for bar in kline_data:
        tr = bar.get("换手率")
        if tr is not None:
            try:
                turnover_series.append({
                    "date": bar.get("日期", ""),
                    "turnover": float(tr),
                })
            except (ValueError, TypeError):
                continue
    # K线数据可能是降序（最新在前），统一按日期升序排列
    turnover_series.sort(key=lambda x: x["date"])

    if not turnover_series:
        return {"error": "K线数据中无有效换手率", "grade": "未知"}

    n = len(turnover_series)
    latest = turnover_series[-1]
    values = [t["turnover"] for t in turnover_series]

    def window_stats(window_days: int) -> dict:
        """计算近N天的换手率统计"""
        w = values[-window_days:] if n >= window_days else values
        if not w:
            return {"mean": None, "std": None, "min": None, "max": None, "count": 0}
        return {
            "mean": round(statistics.mean(w), 4),
            "std": round(statistics.stdev(w), 4) if len(w) >= 2 else None,
            "min": round(min(w), 4),
            "max": round(max(w), 4),
            "count": len(w),
        }

    def percentile_rank(val: float, window_days: int) -> float:
        """当前值在近N天中的分位数（0~1，越高越热）"""
        w = values[-window_days:] if n >= window_days else values
        if not w:
            return None
        below = sum(1 for v in w if v < val)
        return round(below / len(w), 4)

    # 当前值 vs 历史分位
    current_turnover = latest["turnover"]
    pct_5 = percentile_rank(current_turnover, 5)
    pct_10 = percentile_rank(current_turnover, 10)
    pct_20 = percentile_rank(current_turnover, 20)

    # 趋势方向：近5日均值 vs 近20日均值
    w5 = window_stats(5)
    w20 = window_stats(20)
    if w5["mean"] is not None and w20["mean"] is not None:
        if w5["mean"] > w20["mean"] * 1.2:
            trend = "放量加速"
        elif w5["mean"] < w20["mean"] * 0.8:
            trend = "缩量降温"
        else:
            trend = "平稳"
    else:
        trend = "数据不足"

    # 极端信号
    extreme_signal = None
    if pct_20 is not None:
        if pct_20 >= 0.90:
            extreme_signal = "⚠️ 当前换手率处于近20日90%分位以上——过热风险，天量天价"
        elif pct_20 <= 0.10:
            extreme_signal = "ℹ️ 当前换手率处于近20日10%分位以下——极致冷清，地量见地价"

    # 单日分档
    day_result = classify(current_turnover, float_mcap)

    return {
        "date": latest["date"],
        "available_days": n,
        "current": {
            "turnover_pct": round(current_turnover, 4),
            "grade": day_result["grade"],
            "cap_label": day_result["cap_label"],
        },
        "window_5d": w5,
        "window_10d": window_stats(10),
        "window_20d": w20,
        "current_vs_5d_pct": pct_5,
        "current_vs_10d_pct": pct_10,
        "current_vs_20d_pct": pct_20,
        "trend": trend,
        "extreme_signal": extreme_signal,
    }


def main():
    parser = argparse.ArgumentParser(description="换手率分档引擎 v2.0")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    parser.add_argument("--file", type=str, help="JSON 文件路径")
    parser.add_argument("--mode", type=str, default="single",
                        choices=["single", "kline"],
                        help="single: 单日模式(默认), kline: 历史K线模式")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
    elif args.input:
        data = json.loads(args.input)
    else:
        data = json.load(sys.stdin)

    if args.mode == "kline":
        # 历史模式：data 直接是 K线数组，或含 stock.kline 嵌套
        kline = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(kline, dict):
            kline = kline.get("kline", kline.get("data", []))
        stock = data.get("stock", data) if isinstance(data, dict) else {}
        quote = stock.get("quote", {})
        qdata = quote.get("data", quote)
        float_mcap = qdata.get("流通市值")
        result = classify_kline(kline, float(float_mcap) if float_mcap else None)
    else:
        # 单日模式（向后兼容）
        stock = data.get("stock", data)
        quote = stock.get("quote", {})
        qdata = quote.get("data", quote)
        turnover = qdata.get("换手率")
        float_mcap = qdata.get("流通市值")
        if turnover is None:
            print(json.dumps({"error": "quote 缺少 '换手率' 字段", "grade": "未知"}, ensure_ascii=False))
            sys.exit(1)
        result = classify(float(turnover), float(float_mcap) if float_mcap else None)

    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
