"""
数据加载器 —— 统一接口，格式透明，列名校验内置。

解决了 structure_signals.csv（长格式）与 verdict_v7.csv（宽格式）的格式差异问题。
调用方无需关心底层格式——get_structures() 始终返回宽格式 bs_sh/ts_sh/... 列。
"""

import pandas as pd
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"

# ── 列名规范（宽格式） ──────────────────────────────
BS_COLS = {"sh": "bs_sh", "sz": "bs_sz", "cyb": "bs_cyb", "kc": "bs_kc"}
TS_COLS = {"sh": "ts_sh", "sz": "ts_sz", "cyb": "ts_cyb", "kc": "ts_kc"}
INDEX_MAP = {"上证指数": "sh", "深证成指": "sz", "创业板指": "cyb", "科创50": "kc"}
ALL_BS_TS = [f"{pre}_{idx}" for pre in ("bs", "ts") for idx in ("sh", "sz", "cyb", "kc")]


def _validate_columns(df, required, label):
    """校验列名存在——不存在则抛错，不允许沉默返回空值。"""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"{label} 缺少列: {missing}\n"
            f"  实际列: {list(df.columns)}\n"
            f"  → 可能是格式不匹配（长格式 vs 宽格式），详见 A17 反模式。"
        )
    return df


def get_structures() -> pd.DataFrame:
    """
    读取四指数结构信号，始终返回宽格式 DataFrame。

    Returns
    -------
    pd.DataFrame 索引为 date，包含列:
        bs_sh, ts_sh, bs_sz, ts_sz, bs_cyb, ts_cyb, bs_kc, ts_kc
    """
    csv_path = DATA / "structure_signals.csv"
    raw = pd.read_csv(csv_path, parse_dates=["date"])

    # 校验长格式必需列
    _validate_columns(raw, ["index_name", "date", "bottom_structure", "top_structure"],
                      "structure_signals.csv")

    # 长→宽转换，只保留四主要指数
    wide = raw.pivot_table(
        index="date",
        columns="index_name",
        values=["bottom_structure", "top_structure"],
        aggfunc="max"
    ).fillna(0).astype(int)

    # 只取四主要指数列
    keep_cols = [c for c in wide.columns if c[1] in INDEX_MAP]
    wide = wide[keep_cols]

    # 扁平化列名: bottom_structure_上证指数 → bs_sh
    wide.columns = [
        f"{'bs' if 'bottom' in c[0] else 'ts'}_{INDEX_MAP[c[1]]}"
        for c in wide.columns
    ]

    # 补齐缺失的指数列
    for col in ALL_BS_TS:
        if col not in wide.columns:
            wide[col] = 0

    return wide[ALL_BS_TS].sort_index()


def get_verdict() -> pd.DataFrame:
    """
    读取裁决引擎输出，校验必需列名。

    Returns
    -------
    pd.DataFrame（verdict_v7.csv 完整内容）
    """
    csv_path = DATA / "verdict_v7.csv"
    df = pd.read_csv(csv_path, parse_dates=["date"])

    required = ALL_BS_TS + [
        "verdict_main", "verdict_tech", "resonance",
        "close_sh", "close_sz", "close_cyb", "close_kc",
        "regime_sh", "regime_sz", "regime_cyb", "regime_kc",
        "chop_sh", "chop_sz", "chop_cyb", "chop_kc",
        "day_seq_sh", "day_seq_sz", "day_seq_cyb", "day_seq_kc",
        "month_win", "week_win",
    ]
    _validate_columns(df, required, "verdict_v7.csv")
    return df


def get_breadth() -> pd.DataFrame:
    """读取广度引擎输出。"""
    csv_path = DATA / "breadth_daily.csv"
    df = pd.read_csv(csv_path, parse_dates=["date"])
    _validate_columns(df, ["date", "cnhl", "cnhl_ma20", "hl_ratio", "hl_ratio_ma10",
                            "ratio_cross_50"], "breadth_daily.csv")
    return df


def annual_summary(date=None) -> dict:
    """
    某个日期所在年份的结构统计。

    Parameters
    ----------
    date : str or datetime, optional
        基准日期，默认最新。

    Returns
    -------
    dict: {index_code: {"底": n, "顶": m, "最后底": dt, "最后顶": dt}, ...}
    """
    s = get_structures()
    v = get_verdict()

    if date is None:
        date = v["date"].max()
    year = pd.Timestamp(date).year

    s_year = s[s.index.year == year]
    result = {}
    for idx in ("sh", "sz", "cyb", "kc"):
        bs = s_year[s_year[f"bs_{idx}"] == 1].index.tolist()
        ts = s_year[s_year[f"ts_{idx}"] == 1].index.tolist()
        result[idx] = {
            "底": len(bs),
            "顶": len(ts),
            "最后底": bs[-1].strftime("%Y-%m-%d") if bs else "无",
            "最后顶": ts[-1].strftime("%Y-%m-%d") if ts else "无",
        }
    return result


def annual_structure_table(date=None) -> str:
    """打印年内结构全景表（可直接嵌入报告）。"""
    s = annual_summary(date)
    lines = [
        "| 指数 | 底结构次数 | 顶结构次数 | 最后一次顶结构 | 最后一次底结构 |",
        "|------|:--:|:--:|------|------|",
    ]
    names = {"sh": "上证", "sz": "深证", "cyb": "创业板", "kc": "科创50"}
    for idx, name in names.items():
        r = s[idx]
        lines.append(f"| {name} | {r['底']} | {r['顶']} | {r['最后顶']} | {r['最后底']} |")
    return "\n".join(lines)


# ── 自检 ────────────────────────────────────────────
if __name__ == "__main__":
    print("=== loader 自检 ===")
    try:
        s = get_structures()
        print(f"structures: {s.shape[0]} 行, 列: {list(s.columns)}")
        print(f"  2026 年上证顶结构: {s[s.index.year==2026]['ts_sh'].sum()} 次")

        v = get_verdict()
        print(f"verdict: {v.shape[0]} 行, 日期 {v['date'].min().date()}~{v['date'].max().date()}")

        b = get_breadth()
        print(f"breadth: {b.shape[0]} 行")

        print("\n=== 年内结构全景 ===")
        print(annual_structure_table())

        print("\n✅ 自检通过")
    except Exception as e:
        print(f"❌ 自检失败: {e}")
        raise
