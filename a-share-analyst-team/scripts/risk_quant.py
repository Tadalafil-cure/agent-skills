#!/usr/bin/env python3
"""
risk_quant.py — 量化风控指标

输入：日K线 + 基准指数K线（可选）
输出：VaR/CVaR/回撤锥/波动率/Beta/压力测试

用法：
  python risk_quant.py --input '<json>'     # {"symbol_kline": [...], "benchmark_kline": [...]}
"""

import json
import sys
import argparse
import numpy as np
import pandas as pd


def _parse_kline(data) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, dict):
        arr = data.get("data", data.get("kline", []))
        df = pd.DataFrame(arr) if isinstance(arr, list) else pd.DataFrame(data)
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        return pd.DataFrame()

    col_map = {"day": "date", "trade_date": "date", "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    for c in ["close"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return df


def compute_risk_metrics(kline_df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> dict:
    """计算全部风控指标。"""
    if kline_df.empty or len(kline_df) < 30:
        return {"error": "K线数据不足（需 ≥30 日）"}

    close = kline_df["close"]
    returns = close.pct_change().dropna()
    n = len(returns)

    # VaR (历史模拟法)
    var_95 = round(np.percentile(returns, 5) * 100, 2)
    var_99 = round(np.percentile(returns, 1) * 100, 2)
    cvar_95 = round(returns[returns <= np.percentile(returns, 5)].mean() * 100, 2)

    # 年化波动率
    vol_daily = returns.std()
    vol_annual = round(vol_daily * np.sqrt(252), 4)

    # 最大回撤
    cummax = close.expanding().max()
    drawdowns = (close - cummax) / cummax
    max_dd = round(drawdowns.min() * 100, 2)
    max_dd_idx = drawdowns.idxmin()

    # 回撤持续时间
    dd_start = None
    max_duration = 0
    for i in range(len(close)):
        if dd_start is None and close.iloc[i] < cummax.iloc[i]:
            dd_start = i
        elif dd_start is not None and close.iloc[i] >= cummax.iloc[i]:
            duration = i - dd_start
            max_duration = max(max_duration, duration)
            dd_start = None
    if dd_start is not None:
        max_duration = max(max_duration, len(close) - dd_start)

    # 回撤分布
    dd_vals = drawdowns.dropna() * 100
    dd_dist = {
        "p50": round(np.percentile(dd_vals, 50), 1),
        "p75": round(np.percentile(dd_vals, 75), 1),
        "p90": round(np.percentile(dd_vals, 90), 1),
        "p95": round(np.percentile(dd_vals, 95), 1),
    }

    # Beta + 压力测试
    beta = None
    beta_stability = None
    stress_test = {}

    if benchmark_df is not None and not benchmark_df.empty:
        bench_close = benchmark_df["close"]
        bench_returns = bench_close.pct_change().dropna()
        common_idx = returns.index.intersection(bench_returns.index)
        if len(common_idx) >= 30:
            aligned = pd.DataFrame({
                "stock": returns.loc[common_idx],
                "bench": bench_returns.loc[common_idx],
            }).dropna()
            if len(aligned) >= 20:
                cov = aligned.cov().iloc[0, 1]
                var_bench = aligned["bench"].var()
                beta = round(cov / var_bench, 3) if var_bench > 0 else None

                # Beta 稳定性（滚动）
                if len(aligned) >= 60:
                    rolling_betas = []
                    for i in range(60, len(aligned)):
                        window = aligned.iloc[i-60:i]
                        w_cov = window.cov().iloc[0, 1]
                        w_var = window["bench"].var()
                        if w_var > 0:
                            rolling_betas.append(w_cov / w_var)
                    if rolling_betas:
                        beta_std = np.std(rolling_betas)
                        beta_stability = "稳定" if beta_std < 0.2 else "不稳定" if beta_std > 0.5 else "一般"

            # 压力测试
            stress_test = {
                "market_down_10pct": round(beta * -10, 1) if beta else None,
                "market_down_20pct": round(beta * -20, 1) if beta else None,
                "market_down_30pct": round(beta * -30, 1) if beta else None,
            }

    # 风险预算（仓位建议）
    risk_budget = {}
    if abs(var_95) > 0:
        risk_budget["suggested_position_95var"] = round(0.05 / abs(var_95 / 100), 2)  # 以5%日风险为上限
        risk_budget["suggested_position_99var"] = round(0.05 / abs(var_99 / 100), 2) if abs(var_99) > 0 else None

    return {
        "var_95_1d": var_95,
        "var_99_1d": var_99,
        "cvar_95_1d": cvar_95,
        "max_drawdown": max_dd,
        "max_drawdown_duration_days": max_duration,
        "volatility_annual": vol_annual,
        "beta": beta,
        "beta_stability": beta_stability,
        "drawdown_distribution": dd_dist,
        "stress_test": stress_test,
        "risk_budget": risk_budget,
        "data_points": n,
        "latest_price": round(close.iloc[-1], 2),
        "suggested_stop_loss": _compute_stop_loss(kline_df),
    }


def _compute_stop_loss(df: pd.DataFrame) -> dict:
    """机械计算建议止损价。Agent 必须原样引用，禁止心算。"""
    if len(df) < 15:
        return {"error": "数据不足"}
    close = df["close"]
    price = close.iloc[-1]

    # ATR(14)
    high, low = df["high"], df["low"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    # 波动率止损
    vol_daily = close.pct_change().dropna().std()
    var_95 = abs(np.percentile(close.pct_change().dropna(), 5))

    stops = {}
    if not pd.isna(atr) and atr > 0:
        stops["atr_2x"] = round(price - 2 * atr, 2)
        stops["atr_3x"] = round(price - 3 * atr, 2)
    stops["vol_95"] = round(price * (1 - var_95), 2) if var_95 > 0 else None

    # 推荐：ATR-2x 作为默认短线止损
    rec = stops.get("atr_2x")
    if rec is None:
        rec = stops.get("vol_95")
    stops["recommended"] = rec

    return stops


def main():
    parser = argparse.ArgumentParser(description="量化风控")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    args = parser.parse_args()

    data = json.loads(args.input) if args.input else json.load(sys.stdin)

    symbol_kline = _parse_kline(data.get("symbol_kline", data.get("kline", [])))
    benchmark_kline = _parse_kline(data.get("benchmark_kline", data.get("index_kline", []))) if data.get("benchmark_kline") or data.get("index_kline") else None

    result = compute_risk_metrics(symbol_kline, benchmark_kline)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
