#!/usr/bin/env python3
"""
bridge.py — data_package → script input 桥接层

每个脚本需要的数据切片不同，此模块集中管理映射关系。
主 Agent 调用脚本前，用桥接函数从 data_package 抽取正确格式的输入。

用法：
  from bridge import for_ta, for_multi_tf, for_risk_quant, for_theme_detector

  dp = json.load(open("/tmp/data_package.json"))
  ta_input = for_ta(dp)          # → {"data": [...], "quote": {...}}
  mtf_input = for_multi_tf(dp)   # → {"daily": [...], "60min": [...], "30min": [...]}
  risk_input = for_risk_quant(dp) # → {"symbol_kline": [...], "benchmark_kline": [...]}
"""

import json
from typing import Any


def _stock(dp: dict) -> dict:
    return dp.get("stock", {})


def for_ta(dp: dict) -> dict:
    """ta.py 需要 {"data": kline数据, "quote": 实时行情}"""
    s = _stock(dp)
    return {
        "data": s.get("kline_daily", {}).get("data", []),
        "quote": s.get("quote", {}).get("data", {}),
    }


def for_multi_tf(dp: dict) -> dict:
    """multi_tf.py 需要 {"daily": [...], "60min": [...], "30min": [...]}"""
    s = _stock(dp)
    return {
        "daily": s.get("kline_daily", {}).get("data", []),
        "60min": s.get("kline_60min", {}).get("data", []),
        "30min": s.get("kline_30min", {}).get("data", []),
    }


def for_risk_quant(dp: dict) -> dict:
    """risk_quant.py 需要 {"symbol_kline": [...], "benchmark_kline": [...]}"""
    s = _stock(dp)
    return {
        "symbol_kline": s.get("kline_daily", {}).get("data", []),
        "benchmark_kline": s.get("index_kline_000300", {}).get("data", []),
    }


def for_validator(dp: dict) -> dict:
    """validator.py 需要 {"kline": [...], "signal_type": "..."}"""
    s = _stock(dp)
    return {
        "kline": s.get("kline_daily", {}).get("data", []),
        "signal_type": "ma_breakout",
    }
