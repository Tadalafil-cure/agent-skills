#!/usr/bin/env python3
"""
一键构建 · build.py
===================
拉取数据 → 处理 → 输出裁决引擎所需全部 CSV。

用法:
  python data_layer/build.py              # 完整构建（拉取+处理）
  python data_layer/build.py --fetch-only # 仅拉取数据
  python data_layer/build.py --process-only # 仅处理已有数据

依赖: pip install akshare pandas numpy
"""

import sys, os, subprocess
from pathlib import Path


def ensure_deps():
    """检查并安装必要依赖"""
    deps = {"akshare": "akshare", "pandas": "pandas", "numpy": "numpy"}
    missing = []
    for mod, pkg in deps.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"⚠️ 缺少依赖: {', '.join(missing)}")
        print(f"正在安装: pip install {' '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + missing)
        print("✅ 依赖安装完成\n")
    else:
        print("✅ 依赖检查通过 (akshare, pandas, numpy)\n")

# 确保 data_layer 在路径中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch import fetch_all, fetch_all_minute
from process import process_all

OUT_DIR = Path(__file__).resolve().parent.parent / "data"


def main():
    ensure_deps()

    fetch_only = "--fetch-only" in sys.argv
    process_only = "--process-only" in sys.argv

    print("=" * 60)
    print("徐小明裁决引擎 · 数据构建工具 v1.0")
    print("=" * 60)
    print(f"输出目录: {OUT_DIR}")
    print()

    if not process_only:
        raw_path = str(OUT_DIR / "daily_raw.csv")
        fetch_all(raw_path)
        print()
        # 分钟线数据拉取（每次构建都刷新，120天回溯）
        fetch_all_minute(str(OUT_DIR))
        print()

    if not fetch_only:
        process_all()

    print("\n✅ 构建完成。运行裁决引擎:")
    print("   python scripts/verdict_v7.py              # 日线裁决")
    print("   python scripts/verdict_v441.py            # 分钟线修边（需分钟线数据）")


if __name__ == "__main__":
    main()
