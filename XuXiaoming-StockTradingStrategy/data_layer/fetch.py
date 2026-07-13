#!/usr/bin/env python3
"""
数据抽取层 · fetch.py
=====================
从 akshare 抽取 A 股指数日线 + 分钟线 OHLC 数据。

支持的指数：
  上证指数 (sh000001)  深证成指 (sz399001)  创业板指 (sz399006)
  科创50   (sh000688)  沪深300  (sh000300)  中证500  (sh000905)

日线输出：data/daily_raw.csv
分钟线输出：data/minute_raw_{60,30}_{code}_{name}.csv
  (90/120min 由 30min 重采样生成)

依赖：pip install akshare
"""

import pandas as pd
import akshare as ak
from pathlib import Path
import sys
import time

# 指数映射
INDICES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
}

# 日线起点：蒸馏自2019-26，拉到18年初可做一年前置验证
START_DATE = "20180101"

OUT_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch_index_daily(symbol: str, name: str, start_date: str = START_DATE) -> pd.DataFrame:
    """
    拉取单指数日线数据，从 start_date 起。

    Args:
        symbol: akshare 代码 (如 'sh000001')
        name:   中文名称 (如 '上证指数')
        start_date: 起始日期 YYYYMMDD

    Returns:
        DataFrame with columns: date, index_code, index_name, open, high, low, close, volume
    """
    print(f"  拉取 {name} ({symbol})...", end=" ")
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        df["date"] = pd.to_datetime(df["date"])
        df["index_code"] = symbol
        df["index_name"] = name
        df = df.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        })
        cols = ["date", "index_code", "index_name", "open", "high", "low", "close", "volume"]
        result = df[cols].sort_values("date").reset_index(drop=True)
        # 过滤起始日期
        result = result[result["date"] >= pd.Timestamp(start_date)]
        print(f"{len(result)} 行 ({result['date'].min().strftime('%Y-%m-%d')} ~ {result['date'].max().strftime('%Y-%m-%d')})")
        return result
    except Exception as e:
        print(f"❌ {e}")
        return pd.DataFrame()


def fetch_index_minute(symbol: str, name: str, period: str = "60") -> pd.DataFrame:
    """
    拉取单指数分钟线数据（新浪源 ak.stock_zh_a_minute）。

    Args:
        symbol: akshare 格式代码 (如 'sh000001')
        name:   中文名称
        period: 分钟周期，支持 "1"/"5"/"15"/"30"/"60"

    Returns:
        DataFrame: date, open, high, low, close, volume
    """
    try:
        df = ak.stock_zh_a_minute(symbol=symbol, period=period)
        df = df.rename(columns={
            "day": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        raise RuntimeError(f"{name} {period}min 拉取失败: {e}")


def resample_minute(df: pd.DataFrame, target_min: int) -> pd.DataFrame:
    """
    从低周期分钟线重采样到高周期。
    例如 30min → 90min: target_min=90

    Args:
        df:      分钟线 DataFrame（date + OHLCV）
        target_min: 目标周期分钟数

    Returns:
        重采样后的 DataFrame
    """
    df = df.set_index("date")
    rule = f"{target_min}min"
    resampled = df.resample(rule, label="right", closed="right").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    return resampled.dropna().reset_index()


def fetch_all_minute(output_dir: str = None) -> dict:
    """
    拉取五指数分钟线，重采样策略：
      60min → 直接拉取 + 重采样到 120min（120天回溯，2压1精度无损）
      30min → 直接拉取 + 重采样到 90min（60天回溯，3压1）
    降级：单指数失败不阻断整体，记录 errors。

    Returns:
        dict: {"files": [...], "errors": [...]}
    """
    if output_dir is None:
        output_dir = OUT_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 50)
    print("A 股指数分钟线抽取")
    print("  60min(120天回溯) → 120min")
    print("  30min(60天回溯)  → 90min")
    print("=" * 50)

    files = []
    errors = []

    for code, name in INDICES.items():
        min60 = None  # for 120min resample
        min30 = None  # for 90min resample

        # ── 60min + 重采样到 120min ──
        print(f"  {name} 60min→120min...", end=" ")
        try:
            min60 = fetch_index_minute(code, name, "60")
            path60 = str(output_dir / f"minute_raw_60_{code}_{name}.csv")
            min60.to_csv(path60, index=False, encoding="utf-8-sig")
            print(f"60min:{len(min60)}条 ", end="")
            files.append(path60)

            # 60→120: 2根压1根，120天回溯
            min120 = resample_minute(min60, 120)
            path120 = str(output_dir / f"minute_raw_120_{code}_{name}.csv")
            min120.to_csv(path120, index=False, encoding="utf-8-sig")
            files.append(path120)
            print(f"120min:{len(min120)}条 ✓")
        except Exception as e:
            print(f"❌ {e}")
            errors.append(f"{name} 60/120min: {e}")

        time.sleep(0.5)

        # ── 30min + 重采样到 90min ──
        print(f"  {name} 30min→90min...", end=" ")
        try:
            min30 = fetch_index_minute(code, name, "30")
            path30 = str(output_dir / f"minute_raw_30_{code}_{name}.csv")
            min30.to_csv(path30, index=False, encoding="utf-8-sig")
            print(f"30min:{len(min30)}条 ", end="")
            files.append(path30)

            # 30→90: 3根压1根，60天回溯
            min90 = resample_minute(min30, 90)
            path90 = str(output_dir / f"minute_raw_90_{code}_{name}.csv")
            min90.to_csv(path90, index=False, encoding="utf-8-sig")
            files.append(path90)
            print(f"90min:{len(min90)}条 ✓")
        except Exception as e:
            print(f"❌ {e}")
            errors.append(f"{name} 30/90min: {e}")

        time.sleep(0.5)

    print(f"\n✅ 分钟线完成: {len(files)} 文件")
    if errors:
        print(f"⚠️ {len(errors)} 错误: {errors[:3]}...")
    return {"files": files, "errors": errors}


def fetch_all(output_path: str = None) -> pd.DataFrame:
    """
    拉取全部五指数日线，合并输出。

    Args:
        output_path: CSV 输出路径，默认 data/daily_raw.csv

    Returns:
        合并后的 DataFrame
    """
    if output_path is None:
        output_path = str(OUT_DIR / "daily_raw.csv")

    print("=" * 50)
    print("A 股指数日线数据抽取")
    print("=" * 50)

    frames = []
    for symbol, name in INDICES.items():
        df = fetch_index_daily(symbol, name)
        if len(df) > 0:
            frames.append(df)

    if not frames:
        print("❌ 所有指数拉取失败")
        sys.exit(1)

    result = pd.concat(frames, ignore_index=True)
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ 输出: {output_path}")
    print(f"   共 {len(result)} 行, {result['index_name'].nunique()} 指数")
    print(f"   日期范围: {result['date'].min().strftime('%Y-%m-%d')} ~ {result['date'].max().strftime('%Y-%m-%d')}")

    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="A股指数数据抽取")
    p.add_argument("--mode", choices=["daily", "minute", "all"], default="all",
                   help="daily=仅日线, minute=仅分钟线, all=全部 (默认)")
    p.add_argument("--start", default=START_DATE,
                   help=f"日线起始日期 YYYYMMDD (默认: {START_DATE})")
    args = p.parse_args()

    if args.mode in ("daily", "all"):
        fetch_all()
    if args.mode in ("minute", "all"):
        fetch_all_minute()
