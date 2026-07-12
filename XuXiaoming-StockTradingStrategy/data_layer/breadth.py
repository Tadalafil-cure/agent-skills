"""
新高新低分化指标 — v4.5.2 数据中间层
基于 akshare.stock_a_high_low_statistics 适配
公式一: CNHL（累计净新高线）
公式二: HL_Ratio（新高比率）
"""
import numpy as np
import pandas as pd
import akshare as ak
import json
import sys


def fetch_nh_nl() -> pd.DataFrame:
    """从 akshare 拉取每日新高新低家数"""
    raw = ak.stock_a_high_low_statistics()
    df = raw.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df


def build_indicators(df: pd.DataFrame, n_period: int = 60) -> pd.DataFrame:
    """在 NH/NL 基础上计算公式一、公式二"""
    col_nh = f'high{n_period}'
    col_nl = f'low{n_period}'

    if col_nh not in df.columns or col_nl not in df.columns:
        # fallback: 尝试不带数字前缀
        raise KeyError(f"列 {col_nh}/{col_nl} 不存在，可用列: {df.columns.tolist()}")

    out = df[['date', 'close']].copy()
    out['nh'] = df[col_nh].astype(int)
    out['nl'] = df[col_nl].astype(int)

    # ---- 公式一: 净新高 + 累计线 ----
    out['nhl'] = out['nh'] - out['nl']
    out['cnhl'] = out['nhl'].cumsum()
    out['cnhl_ma20'] = out['cnhl'].rolling(20, min_periods=5).mean()

    # ---- 公式二: 新高比率 ----
    denom = (out['nh'] + out['nl']).clip(lower=1)
    out['hl_ratio'] = out['nh'] / denom
    out['hl_ratio_ma10'] = out['hl_ratio'].rolling(10, min_periods=3).mean()

    return out


def make_signal(df: pd.DataFrame) -> dict:
    """根据公式一、公式二给出最新交易日状态判断"""
    last = df.iloc[-1]

    ratio = float(last['hl_ratio'])
    ratio_ma = float(last['hl_ratio_ma10'])
    idx2 = len(df) - 2
    ratio_ma_prev = float(df['hl_ratio_ma10'].iloc[idx2]) if idx2 >= 0 else ratio_ma

    cnhl = float(last['cnhl'])
    cnhl_ma20 = float(last['cnhl_ma20'])
    cnhl_above_ma = cnhl > cnhl_ma20

    # --- 比率状态分级 ---
    if ratio < 0.2:
        ratio_state = "极端弱势"
    elif ratio < 0.5:
        ratio_state = "偏弱"
    elif ratio < 0.8:
        ratio_state = "转强"
    else:
        ratio_state = "强势"

    # --- 上穿0.5检测 ---
    ratio_cross_50 = ratio_ma_prev <= 0.5 < ratio_ma

    # --- 背离判断 ---
    window = 20
    recent = df.iloc[-window:]
    idx_new_low = bool(last['close'] <= recent['close'].min())
    nl_now = float(last['nl'])
    nl_peak = float(recent['nl'].max())
    bullish_div = bool(idx_new_low and nl_now < nl_peak * 0.5)

    divergence = {
        "index_at_new_low": idx_new_low,
        "nl_today": int(nl_now),
        "nl_peak_20d": int(nl_peak),
        "bullish_divergence": bullish_div,
    }

    # --- 综合阶段 ---
    if cnhl_above_ma and ratio_ma > 0.5:
        stage = "切换确认: 个股强于指数"
    elif ratio_cross_50 or (cnhl_above_ma and ratio > 0.5):
        stage = "预备信号: 出现转强迹象, 待确认"
    elif bullish_div:
        stage = "底背离: 下跌动能衰竭, 关注反转"
    else:
        if ratio_ma < 0.3:
            stage = "分化延续: 个股严重弱于指数"
        else:
            stage = "分化延续: 个股仍弱于指数"

    # --- 预备信号记忆（不回撤，供 Agent 判断连续性） ---
    pre_signal_date = None
    days_since_pre = None
    for i in range(len(df) - 1, -1, -1):
        r = df.iloc[i]
        ca_i = float(r['cnhl']) > float(r['cnhl_ma20'])
        rm_i = float(r['hl_ratio_ma10'])
        rr_i = float(r['hl_ratio'])
        rm_prev = float(df['hl_ratio_ma10'].iloc[i-1]) if i > 0 else rm_i
        rc_i = rm_prev <= 0.5 < rm_i
        if rc_i or (ca_i and rr_i > 0.5):
            pre_signal_date = str(r['date'].date())
            days_since_pre = (last['date'] - r['date']).days
            break

    # --- 底背离记忆 ---
    div_signal_date = None
    days_since_div = None
    for i in range(len(df) - 1, -1, -1):
        r = df.iloc[i]
        w_i = df.iloc[max(0,i-19):i+1]
        idx_low_i = bool(float(r['close']) <= float(w_i['close'].min()))
        nl_i = float(r['nl'])
        nl_peak_i = float(w_i['nl'].max())
        if idx_low_i and nl_i < nl_peak_i * 0.5:
            div_signal_date = str(r['date'].date())
            days_since_div = (last['date'] - r['date']).days
            break

    return {
        "date": str(last['date'].date()),
        "stage": stage,
        "hl_ratio": round(ratio, 3),
        "hl_ratio_ma10": round(ratio_ma, 3),
        "ratio_state": ratio_state,
        "ratio_cross_50_today": ratio_cross_50,
        "nhl": int(last['nhl']),
        "cnhl": round(cnhl, 0),
        "cnhl_above_ma20": cnhl_above_ma,
        "nh": int(last['nh']),
        "nl": int(last['nl']),
        "divergence": divergence,
        "period_n": 60,
        # 记忆字段（不改变 stage，供 Agent 交叉验证）
        "last_pre_signal_date": pre_signal_date,
        "days_since_pre_signal": days_since_pre,
        "last_divergence_date": div_signal_date,
        "days_since_divergence": days_since_div,
    }


def analyze(n_period: int = 60) -> dict:
    """一站式入口: 拉数据 → 计算 → 返回结构化 JSON"""
    raw = fetch_nh_nl()
    df = build_indicators(raw, n_period=n_period)
    signal = make_signal(df)
    return signal


# ============ 运行 ============
if __name__ == "__main__":
    print(">>> 拉取 akshare 新高新低数据...")
    raw = fetch_nh_nl()
    print(f"    数据范围: {raw['date'].min().date()} ~ {raw['date'].max().date()}, 共 {len(raw)} 天")

    # 主周期 N=60
    print("\n>>> N=60 计算中...")
    df60 = build_indicators(raw, n_period=60)
    signal60 = make_signal(df60)

    # 辅助周期 N=20
    print(">>> N=20 计算中...")
    df20 = build_indicators(raw, n_period=20)
    signal20 = make_signal(df20)

    # 输出
    print("\n========== N=60 最新信号 ==========")
    print(json.dumps(signal60, ensure_ascii=False, indent=2))

    print("\n========== N=20 最新信号 ==========")
    print(json.dumps(signal20, ensure_ascii=False, indent=2))

    # 最近 10 天 HL_Ratio 趋势
    print("\n========== 近15天 HL_Ratio 趋势 (N=60) ==========")
    recent = df60.tail(15)
    for _, r in recent.iterrows():
        bar = "█" * int(r['hl_ratio_ma10'] * 20) + "░" * (20 - int(r['hl_ratio_ma10'] * 20))
        print(f"  {r['date'].date()}  ratio={r['hl_ratio']:.3f}  MA10={r['hl_ratio_ma10']:.3f}  [{bar}]  NH={int(r['nh']):>4}  NL={int(r['nl']):>4}")

    # 阶段切换检测
    print("\n========== 近期阶段切换事件 (N=60) ==========")
    df60['ratio_cross_50'] = (df60['hl_ratio_ma10'].shift(1) <= 0.5) & (df60['hl_ratio_ma10'] > 0.5)
    df60['ratio_cross_30'] = (df60['hl_ratio_ma10'].shift(1) <= 0.3) & (df60['hl_ratio_ma10'] > 0.3)
    events = df60[(df60['ratio_cross_50'] | df60['ratio_cross_30'])].tail(10)
    for _, r in events.iterrows():
        tag = "上穿0.5 ⬆" if r['ratio_cross_50'] else "上穿0.3 ↑"
        print(f"  {r['date'].date()}  {tag}  MA10={r['hl_ratio_ma10']:.3f}  CNHL={'站上MA20' if r['cnhl'] > r['cnhl_ma20'] else 'MA20下方'}")

    # 底背离事件
    print("\n========== 近期底背离事件 (N=60) ==========")
    for i in range(max(0, len(df60)-60), len(df60)):
        r = df60.iloc[i]
        w = df60.iloc[max(0,i-19):i+1]
        idx_low = bool(r['close'] <= w['close'].min())
        nl_peak = float(w['nl'].max())
        if idx_low and r['nl'] < nl_peak * 0.5:
            print(f"  {r['date'].date()}  指数新低={r['close']:.1f}  NL={int(r['nl'])}  NL峰值20d={int(nl_peak)}  背离!")

    # 保存 CSV
    out_path = "data/breadth_daily.csv"
    df60.to_csv(out_path, index=False)
    print(f"\n>>> 已保存至 {out_path}")
