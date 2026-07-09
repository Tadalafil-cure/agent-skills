#!/usr/bin/env python3
"""ta.py 单元测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import json
import pandas as pd
import numpy as np
from ta import _parse_kline, compute_all, compute_ma, compute_macd, compute_rsi, compute_kdj, compute_bollinger


def make_kline(n=120, trend="up", seed=42):
    """生成模拟 K 线数据。"""
    np.random.seed(seed)
    base = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    if trend == "up":
        drift = np.linspace(0, 30, n)
    elif trend == "down":
        drift = np.linspace(0, -30, n)
    else:
        drift = np.sin(np.linspace(0, 4 * np.pi, n)) * 10

    close = base + drift + np.random.randn(n) * 2
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": close - np.random.rand(n) * 2,
        "high": close + np.random.rand(n) * 3,
        "low": close - np.random.rand(n) * 3,
        "close": close,
        "volume": np.random.randint(1e6, 1e7, n),
    })
    # Ensure open/high/low/close consistency
    for i in range(n):
        df.loc[i, "high"] = max(df.loc[i, "open"], df.loc[i, "close"], df.loc[i, "high"])
        df.loc[i, "low"] = min(df.loc[i, "open"], df.loc[i, "close"], df.loc[i, "low"])
    return df


def test_parse_kline():
    """测试 K 线解析。"""
    df = make_kline(120)
    parsed = _parse_kline(df)
    assert len(parsed) == 120
    assert "close" in parsed.columns
    print("  ✓ test_parse_kline passed")


def test_compute_ma():
    """测试均线计算。"""
    df = make_kline(120, "up")
    result = compute_ma(df)
    assert "MA5" in result
    assert "MA20" in result
    assert "arrangement" in result
    print(f"  ✓ test_compute_ma passed (arrangement={result['arrangement']})")


def test_compute_macd():
    """测试 MACD 计算。"""
    df = make_kline(120, "up")
    result = compute_macd(df)
    assert "DIF" in result
    assert "DEA" in result
    assert "signal" in result
    print(f"  ✓ test_compute_macd passed (signal={result['signal']})")


def test_compute_rsi():
    """测试 RSI 计算。"""
    df = make_kline(120)
    result = compute_rsi(df)
    assert "value" in result
    assert "zone" in result
    print(f"  ✓ test_compute_rsi passed (RSI={result['value']}, zone={result['zone']})")


def test_compute_kdj():
    """测试 KDJ 计算。"""
    df = make_kline(120)
    result = compute_kdj(df)
    assert "K" in result
    assert "D" in result
    assert "J" in result
    print(f"  ✓ test_compute_kdj passed (signal={result.get('signal')})")


def test_compute_bollinger():
    """测试布林带计算。"""
    df = make_kline(120)
    result = compute_bollinger(df)
    assert "upper" in result
    assert "mid" in result
    assert "lower" in result
    assert "position" in result
    print(f"  ✓ test_compute_bollinger passed (position={result['position']})")


def test_compute_all():
    """测试全量计算。"""
    df = make_kline(120, "up")
    result = compute_all(df)
    assert "ma" in result
    assert "macd" in result
    assert "rsi" in result
    assert "kdj" in result
    assert "boll" in result
    assert "atr" in result
    assert "volume" in result
    assert "candlestick" in result
    assert "price" in result
    print(f"  ✓ test_compute_all passed ({len(result)} sections)")


if __name__ == "__main__":
    print("Running ta.py tests...")
    test_parse_kline()
    test_compute_ma()
    test_compute_macd()
    test_compute_rsi()
    test_compute_kdj()
    test_compute_bollinger()
    test_compute_all()
    print("All tests passed ✓")
