#!/usr/bin/env python3
"""
earnings_surprise.py — 业绩预期差

⚠️ 当前状态：暂缓。依赖第二中间层提供实际财报数据（净利润/营收等）。
  盈利预测数据来自 get_profit_forecast_*，但对比所需的实际业绩数据待财务中间层就绪。

预计输入：盈利预测数据 + 实际财报数据
预计输出：{
    "latest_quarter": "2026Q1",
    "forecast_eps": 5.20,
    "actual_eps": 5.45,
    "surprise_pct": 4.8,
    "surprise_direction": "beat",
    "historical_beat_rate": 0.75,
    "guidance_change": "上调"
}
"""

import json
import sys

def compute_earnings_surprise(forecast: dict, actuals: dict) -> dict:
    return {
        "error": "earnings_surprise 暂不可用",
        "reason": "依赖第二中间层提供实际财报数据（净利润/营收），当前财务中间层未就绪",
        "deferred_until": "第二中间层 8 函数搬迁完成后",
    }

if __name__ == "__main__":
    print(json.dumps(compute_earnings_surprise({}, {}), ensure_ascii=False))
