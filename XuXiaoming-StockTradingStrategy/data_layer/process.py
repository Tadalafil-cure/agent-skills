#!/usr/bin/env python3
"""
数据处理层 · process.py
=======================
将 daily_raw.csv 处理为裁决引擎所需的全部 CSV 文件。

流水线：
  1. daily_raw.csv → 按指数拆分 + 运行 structure_engine → structure_signals.csv
  2. daily_raw.csv → 运行 sequence_engine → turn_sequence_events.csv
  3. structure_signals.csv → 运行 verdict_v7 → verdict_v7.csv (含多指数共振)
  4. (可选) 分钟线数据 → 运行 minute_structure_v2 → minute_structure_v2_{sh,sz}.csv

依赖：已拉取 daily_raw.csv（通过 fetch.py）
"""

import pandas as pd
import numpy as np
import sys, os
from pathlib import Path

# 添加 scripts 到路径
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from structure_engine import process_structure

OUT_DIR = Path(__file__).resolve().parent.parent / "data"


def make_structure_signals(raw_path: str) -> str:
    """
    步骤1: 从 daily_raw.csv 生成 structure_signals.csv

    对每个指数运行 MACD(4,30,4) 钝化→结构判定。
    输出列: index_name, date, close, high, low, bottom_structure, top_structure, bottom_divergence
    """
    print("\n[1/4] 结构信号计算...")

    df = pd.read_csv(raw_path)
    df["date"] = pd.to_datetime(df["date"])

    rows = []
    for name in df["index_name"].unique():
        sub = df[df["index_name"] == name].copy().sort_values("date").reset_index(drop=True)
        if len(sub) < 30:
            print(f"  ⚠️ {name} 数据不足 ({len(sub)}天)")
            continue

        sub = process_structure(sub)
        bs = sub.get("bottom_structure", pd.Series(0, index=sub.index)).sum()
        ts = sub.get("top_structure", pd.Series(0, index=sub.index)).sum()

        for _, r in sub.iterrows():
            rows.append({
                "index_name": name,
                "date": r["date"].strftime("%Y-%m-%d"),
                "close": r["close"],
                "high": r["high"],
                "low": r["low"],
                "bottom_structure": int(r.get("bottom_structure", 0)),
                "top_structure": int(r.get("top_structure", 0)),
                "bottom_divergence": int(r.get("bottom_divergence", 0)),
            })
        print(f"  {name}: bs={int(bs)}, ts={int(ts)}")

    out = pd.DataFrame(rows)
    out_path = str(OUT_DIR / "structure_signals.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  ✅ {out_path} ({len(out)}行)")
    return out_path


def make_sequence_events(raw_path: str) -> str:
    """
    步骤2: 从 daily_raw.csv 生成 turn_sequence_events.csv

    对每个指数计算九转序列（日/周/月），输出序列事件。
    输出列: index_name, date, period, seq_type, seq_value
    """
    print("\n[2/4] 九转序列计算...")

    df = pd.read_csv(raw_path)
    df["date"] = pd.to_datetime(df["date"])

    rows = []
    for name in df["index_name"].unique():
        sub = df[df["index_name"] == name].copy().sort_values("date").reset_index(drop=True)
        if len(sub) < 30:
            continue

        close = sub["close"].values
        dates = sub["date"].values

        # 日线九转：收盘价 vs 4根前收盘价
        td = np.zeros(len(close), dtype=int)
        td[0] = 1
        for i in range(1, len(close)):
            if close[i] > close[max(0, i - 4)]:
                if td[i - 1] > 0:
                    td[i] = td[i - 1] + 1
                else:
                    td[i] = 1
            elif close[i] < close[max(0, i - 4)]:
                if td[i - 1] < 0:
                    td[i] = td[i - 1] - 1
                else:
                    td[i] = -1
            else:
                td[i] = 0  # 相等断裂

        for i in range(len(td)):
            if abs(td[i]) >= 8:
                seq_type = "高9" if td[i] > 0 else "低9"
                rows.append({
                    "index_name": name,
                    "date": pd.Timestamp(dates[i]).strftime("%Y-%m-%d"),
                    "period": "日线",
                    "seq_type": seq_type,
                    "seq_value": abs(td[i]),
                })

        # 周线九转（用周五数据近似）
        sub["week"] = sub["date"].dt.isocalendar().week
        sub["year"] = sub["date"].dt.isocalendar().year
        weekly = sub.groupby(["year", "week"]).agg(
            close=("close", "last"),
            date=("date", "last")
        ).reset_index().sort_values("date")

        wclose = weekly["close"].values
        wdates = weekly["date"].values
        wtd = np.zeros(len(wclose), dtype=int)
        if len(wclose) > 1:
            wtd[0] = 1
            for i in range(1, len(wclose)):
                if wclose[i] > wclose[max(0, i - 4)]:
                    wtd[i] = wtd[i - 1] + 1 if wtd[i - 1] > 0 else 1
                elif wclose[i] < wclose[max(0, i - 4)]:
                    wtd[i] = wtd[i - 1] - 1 if wtd[i - 1] < 0 else -1
                else:
                    wtd[i] = 0

            for i in range(len(wtd)):
                if abs(wtd[i]) >= 8:
                    seq_type = "高9" if wtd[i] > 0 else "低9"
                    rows.append({
                        "index_name": name,
                        "date": pd.Timestamp(wdates[i]).strftime("%Y-%m-%d"),
                        "period": "周线",
                        "seq_type": seq_type,
                        "seq_value": abs(wtd[i]),
                    })

        # 月线九转
        sub["month"] = sub["date"].dt.month
        sub["year_m"] = sub["date"].dt.year
        monthly = sub.groupby(["year_m", "month"]).agg(
            close=("close", "last"),
            date=("date", "last")
        ).reset_index().sort_values("date")

        mclose = monthly["close"].values
        mdates = monthly["date"].values
        mtd = np.zeros(len(mclose), dtype=int)
        if len(mclose) > 1:
            mtd[0] = 1
            for i in range(1, len(mclose)):
                if mclose[i] > mclose[max(0, i - 4)]:
                    mtd[i] = mtd[i - 1] + 1 if mtd[i - 1] > 0 else 1
                elif mclose[i] < mclose[max(0, i - 4)]:
                    mtd[i] = mtd[i - 1] - 1 if mtd[i - 1] < 0 else -1
                else:
                    mtd[i] = 0

            for i in range(len(mtd)):
                if abs(mtd[i]) >= 8:
                    seq_type = "高9" if mtd[i] > 0 else "低9"
                    rows.append({
                        "index_name": name,
                        "date": pd.Timestamp(mdates[i]).strftime("%Y-%m-%d"),
                        "period": "月线",
                        "seq_type": seq_type,
                        "seq_value": abs(mtd[i]),
                    })

        print(f"  {name}: 日线序列 {sum(1 for r in rows if r['index_name']==name and r['period']=='日线')} 段")

    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["index_name", "date", "period"])
    out_path = str(OUT_DIR / "turn_sequence_events.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  ✅ {out_path} ({len(out)}行)")
    return out_path


def make_verdict(struct_path: str = None) -> str:
    """
    步骤3: 运行裁决引擎 v7，生成 verdict_v7.csv + multi_index_resonance.csv

    调用 scripts/verdict_v7.py
    """
    print("\n[3/4] 裁决引擎 v7...")

    # 运行 verdict_v7.py
    import subprocess
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "verdict_v7.py")],
        cwd=str(SCRIPT_DIR.parent),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ⚠️ verdict_v7 运行出错:\n{result.stderr[:500]}")
    else:
        lines = result.stdout.strip().split("\n")
        for line in lines[-5:]:
            print(f"  {line}")

    out_path = str(OUT_DIR / "verdict_v7.csv")
    if os.path.exists(out_path):
        v7 = pd.read_csv(out_path)
        print(f"  ✅ {out_path} ({len(v7)}天)")
        return out_path
    else:
        print(f"  ❌ {out_path} 未生成")
        return ""


def make_minute_structures() -> list:
    """
    步骤4: (可选) 运行分钟线结构引擎

    自动搜索分钟线数据：优先 data_layer 产出 (data/minute_raw_*.csv)，
    回退到旧格式 (data/min*.csv)。无数据时跳过。
    可通过环境变量 MINUTE_DATA_DIR 指定外部数据目录。
    """
    print("\n[4/4] 分钟线结构 (可选)...")

    # 搜索路径：skill 自身 data/ + 可选外部目录
    search_dirs = [OUT_DIR]
    ext_dir = os.environ.get("MINUTE_DATA_DIR", "")
    if ext_dir:
        search_dirs.append(Path(ext_dir))

    # 检查是否有分钟线数据（任意格式）
    has_minute = False
    for d in search_dirs:
        if list(d.glob("minute_raw_60_*.csv")) or list(d.glob("min60_*.csv")) or list(d.glob("minute_raw_30_*.csv")):
            has_minute = True
            break

    if not has_minute:
        print("  ⚠️ 无分钟线数据，跳过。")
        print("  拉取: python data_layer/fetch.py --mode minute")
        print("  或设置 MINUTE_DATA_DIR 指向外部分钟线目录。")
        return []

    import subprocess
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "minute_structure_v2.py"),
         "--data-dir", str(search_dirs[0])],
        cwd=str(SCRIPT_DIR.parent),
        capture_output=True, text=True
    )
    for line in result.stdout.strip().split("\n")[-5:]:
        print(f"  {line}")

    outputs = [
        str(OUT_DIR / "minute_structure_v2_sh.csv"),
        str(OUT_DIR / "minute_structure_v2_sz.csv"),
    ]
    for p in outputs:
        if os.path.exists(p):
            print(f"  ✅ {p}")
    return [p for p in outputs if os.path.exists(p)]


def process_all(raw_path: str = None):
    """完整处理流水线"""
    if raw_path is None:
        raw_path = str(OUT_DIR / "daily_raw.csv")

    if not os.path.exists(raw_path):
        print(f"❌ {raw_path} 不存在，请先运行 fetch.py")
        sys.exit(1)

    print("=" * 50)
    print("数据处理流水线")
    print("=" * 50)

    out_dir = OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    files = []
    files.append(make_structure_signals(raw_path))
    files.append(make_sequence_events(raw_path))
    files.append(make_verdict())
    files.extend(make_minute_structures())

    print("\n" + "=" * 50)
    print("流水线完成")
    print("=" * 50)
    for f in files:
        if f:
            print(f"  ✅ {f}")
    print(f"\n共生成 {len([f for f in files if f])} 个数据文件")


if __name__ == "__main__":
    process_all()
