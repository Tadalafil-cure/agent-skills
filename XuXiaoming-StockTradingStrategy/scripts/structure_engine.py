#!/usr/bin/env python3
"""
操作层 · 结构判定引擎
基于 MACD(4,30,4) 检测钝化→结构形成→结构消失的完整生命周期。

徐小明核心规则：
1. 钝化 = 价格创新高/低，但 DIF(4,30,4) 未同步 → 潜在结构
2. 结构形成 = 钝化后 DIF 反向拐头 → 触发操作信号
3. 结构消失 = 钝化消失（DIF 再次同向）→ 纠错
4. 一切以收盘价确认
"""

import pandas as pd
import numpy as np


def calc_macd_4_30_4(df: pd.DataFrame) -> pd.DataFrame:
    """MACD(4,30,4) —— 徐小明用于结构判定的专用参数"""
    ema4 = df["close"].ewm(span=4, adjust=False).mean()
    ema30 = df["close"].ewm(span=30, adjust=False).mean()
    df["dif_4"] = ema4 - ema30
    df["dea_4"] = df["dif_4"].ewm(span=4, adjust=False).mean()
    df["bar_4"] = 2 * (df["dif_4"] - df["dea_4"])
    return df


def calc_macd_default(df: pd.DataFrame) -> pd.DataFrame:
    """MACD(12,26,9) —— 默认参数，用于趋势判断"""
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["dif"] = ema12 - ema26
    df["dea"] = df["dif"].ewm(span=9, adjust=False).mean()
    df["macd_bar"] = 2 * (df["dif"] - df["dea"])
    return df


def detect_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    钝化检测（v4.6.11: lookback 40→20，极值法）
    
    顶部钝化：当前价格创 lookback 日内新高，但 DIF_4 未创 lookback 日内新高
    底部钝化：当前价格创 lookback 日内新低，但 DIF_4 未创 lookback 日内新低

    lookback=20：约一个月的交易日。日线钝化→结构 30d 转化率 87-95%，假信号 5-15%。
    钝化不入裁决，仅用于分析层，20d 灵敏度优先于精确度。
    """
    n = len(df)
    top_div = [0] * n
    bot_div = [0] * n

    for i in range(lookback, n):
        # 顶部钝化
        price_peak = df["high"].iloc[i - lookback:i].max()
        dif_peak = df["dif_4"].iloc[i - lookback:i].max()
        if df["high"].iloc[i] >= price_peak and df["dif_4"].iloc[i] < dif_peak:
            top_div[i] = 1

        # 底部钝化
        price_trough = df["low"].iloc[i - lookback:i].min()
        dif_trough = df["dif_4"].iloc[i - lookback:i].min()
        if df["low"].iloc[i] <= price_trough and df["dif_4"].iloc[i] > dif_trough:
            bot_div[i] = 1

    df["top_divergence"] = top_div
    df["bottom_divergence"] = bot_div
    return df


def detect_structure(df: pd.DataFrame) -> pd.DataFrame:
    """
    结构形成检测。

    顶部结构：钝化出现后，DIF_4 向下拐头（今天 < 昨天）
    底部结构：钝化出现后，DIF_4 向上拐头（今天 > 昨天）

    同时跟踪钝化的"级别"——DIF 距前高的差距越大，钝化级别越大。
    """
    n = len(df)
    top_struct = [0] * n
    bot_struct = [0] * n
    div_magnitude = [0.0] * n  # 钝化级别（DIF 差值/价格比例）

    # 追踪钝化是否持续
    in_top_div = False
    in_bot_div = False
    top_div_start_idx = -1
    bot_div_start_idx = -1

    for i in range(1, n):
        # 钝化开始
        if df["top_divergence"].iloc[i] == 1 and not in_top_div:
            in_top_div = True
            top_div_start_idx = i
            in_bot_div = False

        if df["bottom_divergence"].iloc[i] == 1 and not in_bot_div:
            in_bot_div = True
            bot_div_start_idx = i
            in_top_div = False

        # 钝化中 → 检测结构形成（DIF 拐头）
        if in_top_div:
            if df["dif_4"].iloc[i] < df["dif_4"].iloc[i - 1]:
                top_struct[i] = 1
                in_top_div = False
                # 计算钝化级别：钝化期间 DIF 距前高的最大差距
                if top_div_start_idx > 0:
                    dif_at_start = df["dif_4"].iloc[top_div_start_idx]
                    dif_at_peak = df["dif_4"].iloc[top_div_start_idx:i].max()
                    div_magnitude[i] = abs(dif_at_peak - dif_at_start)

        if in_bot_div:
            if df["dif_4"].iloc[i] > df["dif_4"].iloc[i - 1]:
                bot_struct[i] = 1
                in_bot_div = False
                if bot_div_start_idx > 0:
                    dif_at_start = df["dif_4"].iloc[bot_div_start_idx]
                    dif_at_trough = df["dif_4"].iloc[bot_div_start_idx:i].min()
                    div_magnitude[i] = abs(dif_at_start - dif_at_trough)

        # 钝化消失（价格不再创新高/低 或 DIF 已经同步）
        if in_top_div and df["top_divergence"].iloc[i] == 0:
            # 连续多日无钝化 → 钝化消失
            if i - top_div_start_idx > 3:
                in_top_div = False

        if in_bot_div and df["bottom_divergence"].iloc[i] == 0:
            if i - bot_div_start_idx > 3:
                in_bot_div = False

    df["top_structure"] = top_struct
    df["bottom_structure"] = bot_struct
    df["divergence_magnitude"] = div_magnitude

    # 钝化级别定性
    df["divergence_level"] = np.select(
        [df["divergence_magnitude"] > df["divergence_magnitude"].quantile(0.67),
         df["divergence_magnitude"] > df["divergence_magnitude"].quantile(0.33),
         df["divergence_magnitude"] > 0],
        [3, 2, 1],
        default=0
    )  # 0=无, 1=小, 2=中, 3=大

    return df


def detect_structure_lifecycle(df: pd.DataFrame) -> pd.DataFrame:
    """
    结构生命周期状态机。

    状态：
    0 = 无信号（正常状态）
    1 = 钝化中（准备状态——"准备资金""重点观察"）
    2 = 结构形成（操作触发——"按规则买入/卖出"）
    3 = 等待结果（结构形成后，等钝化消失或趋势突破——"多看少动"）

    附加：
    - 二次钝化：结构形成后再次出现同向钝化
    - 钝化消失：钝化期间 DIF 同步创新高/低 → 钝化失效
    """
    n = len(df)
    state = [0] * n
    is_double = [0] * n       # 二次钝化标记
    divergence_lost = [0] * n  # 钝化消失标记

    current_state = 0
    last_struct_idx = -1

    for i in range(1, n):
        if current_state == 0:
            # 无信号 → 钝化出现
            if df["top_divergence"].iloc[i] == 1 or df["bottom_divergence"].iloc[i] == 1:
                current_state = 1

        elif current_state == 1:
            # 钝化中 → 结构形成
            if df["top_structure"].iloc[i] == 1 or df["bottom_structure"].iloc[i] == 1:
                current_state = 2
                last_struct_idx = i
            # 钝化中 → 钝化消失（DIF 创新高/低）
            elif (df["top_divergence"].iloc[i] == 0 and df["bottom_divergence"].iloc[i] == 0):
                # 钝化持续多日后突然消失
                divergence_lost[i] = 1
                current_state = 0

        elif current_state == 2:
            # 结构形成后 → 等待结果
            current_state = 3

        elif current_state == 3:
            # 等待结果中 → 出现二次钝化
            if df["top_divergence"].iloc[i] == 1 or df["bottom_divergence"].iloc[i] == 1:
                is_double[i] = 1
                current_state = 1  # 回到钝化状态
            # 等待结果中 → 钝化消失（纠错）
            elif divergence_lost[i] == 1:
                current_state = 0

        state[i] = current_state

    df["structure_state"] = state
    df["is_double_divergence"] = is_double
    df["divergence_lost"] = divergence_lost

    return df


def process_structure(df: pd.DataFrame) -> pd.DataFrame:
    """完整结构判定流水线"""
    df = calc_macd_default(df)
    df = calc_macd_4_30_4(df)
    df = detect_divergence(df)
    df = detect_structure(df)
    df = detect_structure_lifecycle(df)
    return df


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "data/daily_ma_channels.csv"

    print(f"读取 {path}...")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])

    # 只处理上证指数
    sz = df[df["index_code"] == "sh000001"].copy().reset_index(drop=True)
    sz = process_structure(sz)

    # 统计
    print("\n结构信号统计（上证指数，2019-2026）:")
    for label, col in [("顶部结构", "top_structure"), ("底部结构", "bottom_structure")]:
        count = sz[col].sum()
        # 列出信号日期
        dates = sz[sz[col] == 1]["date"].dt.strftime("%Y-%m-%d").tolist()
        print(f"  {label}: {int(count)} 次")
        for d in dates:
            print(f"    {d}")

    print(f"\n结构状态分布:")
    for s, label in [(0, "无信号"), (1, "钝化中"), (2, "结构形成"), (3, "等待结果")]:
        cnt = (sz["structure_state"] == s).sum()
        print(f"  状态{s} ({label}): {cnt} 天 ({cnt/len(sz)*100:.1f}%)")
