#!/usr/bin/env python3
"""
factor_quality.py — A股因子质量分析引擎 v0.1

独立前置模块。按指数面板评估 14 个技术因子的有效性。
输出 IV / PSI / Spearman IC / 相关性矩阵 / 综合评级。

用法:
  python factor_quality.py --update-panels          # 更新全部指数面板
  python factor_quality.py --panel 科创50            # 更新指定指数
  python factor_quality.py --stock 600519            # 个股时序因子质量
  python factor_quality.py --stock 600519 --force    # 强制重跑忽略缓存
"""

import argparse
import json
import os
import sys
import time
import random
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── 路径配置 ──────────────────────────────────────────────
SKILL_DIR = Path(__file__).resolve().parent
DATA_DIR = SKILL_DIR / "data"
PANELS_DIR = DATA_DIR / "panels"
STOCKS_DIR = DATA_DIR / "stocks"
PANELS_DIR.mkdir(parents=True, exist_ok=True)
STOCKS_DIR.mkdir(parents=True, exist_ok=True)

LOOKBACK = 252          # 回看交易日数
FORWARD = 22            # 前瞻交易日数（≈30日历日）
MIN_SAMPLES = 230       # 最小有效行数
N_BINS_IV = 10          # IV分箱数
PSI_SPLITS = 3          # PSI时间等分数
CORR_THRESHOLD = 0.7    # 相关性去重阈值
MAX_WORKERS = 2          # 同源并发 ≤2（遵守中间层调用规则）
SAMPLE_LIMIT = 300      # 大指数抽样上限（分3批×100只拉取，合并分析）

# ── 指数定义 ──────────────────────────────────────────────
INDEX_DEFS = {
    # ── 大盘桶 ──
    "沪深300":  {"code": "000300", "desc": "大盘蓝筹"},
    "中证A500": {"code": "000510", "desc": "全市场大中盘"},
    # ── 中小盘桶 ──
    "中证500":  {"code": "000905", "desc": "中盘"},
    "中证1000": {"code": "000852", "desc": "中小盘"},
    # ── 科技桶 · 候选 ──
    "科技桶":   {"code": "000688,399673", "desc": "科创50+创业板50合并"},
    "科创50":   {"code": "000688", "desc": "科创板中大市值"},
    "创业板50": {"code": "399673", "desc": "创业板大市值"},
    "科创100":  {"code": "000698", "desc": "科创板51-150"},
    "创业板100":{"code": "399004", "desc": "创业板大盘"},
    "科创创业50":{"code": "931643", "desc": "科创+创业跨板50"},
    # ── 保留 ──
    "创业板指": {"code": "399006", "desc": "创业板大中市值"},
}


# ═══════════════════════════════════════════════════════════
# 因子计算（从 OHLCV DataFrame 逐日计算全序列）
# ═══════════════════════════════════════════════════════════

def sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均。"""
    return series.rolling(window=period).mean()

def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均。"""
    return series.ewm(span=period, adjust=False).mean()

def compute_all_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    输入: K线 DataFrame (date, open, high, low, close, volume)
    输出: 相同 index 的因子 DataFrame，含全部 14 个因子列
    """
    close = df["close"].astype(float)
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)
    vol   = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0, index=df.index)
    
    factors = pd.DataFrame(index=df.index)
    
    # F1: MA20偏离率
    ma20 = sma(close, 20)
    factors["ma20_div"] = (close - ma20) / ma20.replace(0, np.nan)
    
    # F2: MA5/MA20 ratio
    ma5 = sma(close, 5)
    factors["ma5_ma20_ratio"] = ma5 / ma20.replace(0, np.nan)
    
    # F3: RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    factors["rsi14"] = 100 - (100 / (1 + rs))
    
    # F4-F5: MACD
    dif = ema(close, 12) - ema(close, 26)
    dea = ema(dif, 9)
    factors["macd_hist"] = 2 * (dif - dea)
    factors["macd_dif_dea_gap"] = (dif - dea) / close.replace(0, np.nan)
    
    # F6-F7: KDJ
    low_n  = low.rolling(9).min()
    high_n = high.rolling(9).max()
    rsv = ((close - low_n) / (high_n - low_n).replace(0, 1e-10)) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    factors["kdj_k"] = k
    factors["kdj_j"] = 3 * k - 2 * d
    
    # F8-F9: 布林带
    bb_mid = sma(close, 20)
    bb_std = close.rolling(20).std(ddof=0)
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    factors["boll_position"] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
    factors["boll_bandwidth"] = (bb_upper - bb_lower) / bb_mid.replace(0, np.nan)
    
    # F10: 量比
    vol_ma20 = sma(vol, 20)
    factors["vol_ratio"] = vol / vol_ma20.replace(0, np.nan)
    
    # F11: ADX(14)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.ewm(span=14, adjust=False).mean()
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr14.replace(0, 1e-10)
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr14.replace(0, 1e-10)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
    factors["adx"] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    # F12: ATR%
    factors["atr_pct"] = atr14 / close.replace(0, np.nan)
    
    # F13-F14: 动量
    factors["ret_5d"] = close / close.shift(5) - 1
    factors["ret_20d"] = close / close.shift(20) - 1
    
    return factors


# ═══════════════════════════════════════════════════════════
# 数据获取
# ═══════════════════════════════════════════════════════════

def get_index_constituents(index_name: str) -> list[str]:
    """拉指数成分股代码列表（akshare）。支持单指数和组合指数（code用逗号分隔）。"""
    import akshare as ak
    idx_spec = INDEX_DEFS[index_name]["code"]
    all_codes = []
    for idx_code in idx_spec.split(","):
        df = ak.index_stock_cons(symbol=idx_code.strip())
        codes = df["品种代码"].astype(str).tolist()
        codes = [c.replace("sh", "").replace("sz", "").replace("bj", "") for c in codes]
        all_codes.extend(codes)
    # 去重（同只股票可能跨指数）
    seen = set()
    uniq = []
    for c in all_codes:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq

def fetch_kline(code: str) -> Optional[pd.DataFrame]:
    """拉单只股票日K线（中间层），取最近 365 日历日 ≈ 252 交易日。"""
    from a_share_market_middleware.stock.kline import get_daily_kline
    try:
        result = get_daily_kline(code)  # 默认365日历日，与 LOOKBACK=252 交易日匹配
        if not result.get("success"):
            return None
        data = result.get("data", [])
        if not data:
            return None
        df = pd.DataFrame(data)
        # 统一列名
        col_map = {"日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
                    "最低": "low", "成交量": "volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        for c in ["open", "high", "low", "close"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        return df if len(df) >= 60 else None  # 至少60天数据
    except Exception:
        return None

def fetch_klines_parallel(codes: list[str], max_workers: int = MAX_WORKERS) -> dict[str, pd.DataFrame]:
    """并发拉多只股票K线。遵守中间层调用规则：同源并发≤2，提交间隔1~2s。"""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for code in codes:
            futures[executor.submit(fetch_kline, code)] = code
            time.sleep(random.uniform(1.0, 2.0))  # 提交间隔1~2s
        for future in as_completed(futures):
            code = futures[future]
            try:
                df = future.result()
                if df is not None:
                    results[code] = df
            except Exception:
                pass
    return results


# ═══════════════════════════════════════════════════════════
# 面板构建
# ═══════════════════════════════════════════════════════════

def build_panel(kline_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    输入: {code: K线DataFrame}
    输出: 面板 DataFrame, columns = [date, stock, f1..f14, target]
    """
    rows = []
    for code, df in kline_dict.items():
        factors = compute_all_factors(df)
        # 目标: 30日后涨跌方向
        close = df["close"].astype(float)
        fwd_return = close.shift(-FORWARD) / close - 1
        target = (fwd_return > 0).astype(int)
        
        panel_df = pd.DataFrame({
            "date": df["date"],
            "stock": code,
            "target": target,
        })
        for col in factors.columns:
            panel_df[col] = factors[col].values
        
        # 只保留 target 有效的行（最后 FORWARD 天无 target）
        panel_df = panel_df.dropna(subset=["target"])
        rows.append(panel_df)
    
    if not rows:
        return pd.DataFrame()
    panel = pd.concat(rows, ignore_index=True)
    # 按时序排列（PSI依赖时间顺序）
    if "date" in panel.columns:
        panel = panel.sort_values(["stock", "date"]).reset_index(drop=True)
    # 去因子缺失行
    factor_cols = [c for c in panel.columns if c not in ("date", "stock", "target")]
    panel = panel.dropna(subset=factor_cols, thresh=len(factor_cols)//2)
    return panel


# ═══════════════════════════════════════════════════════════
# 统计分析
# ═══════════════════════════════════════════════════════════

FACTOR_NAMES = {
    "ma20_div": "MA20偏离率", "ma5_ma20_ratio": "MA5/MA20比",
    "rsi14": "RSI(14)", "macd_hist": "MACD柱", "macd_dif_dea_gap": "MACD距离",
    "kdj_k": "KDJ-K", "kdj_j": "KDJ-J",
    "boll_position": "布林位置", "boll_bandwidth": "布林带宽",
    "vol_ratio": "量比", "adx": "ADX趋势", "atr_pct": "ATR波动率",
    "ret_5d": "5日动量", "ret_20d": "20日动量",
}

def compute_iv(panel: pd.DataFrame, factor_col: str, target_col: str = "target", bins: int = None) -> float:
    """计算单因子 IV。"""
    if bins is None:
        bins = N_BINS_IV
    data = panel[[factor_col, target_col]].dropna()
    if len(data) < 100:
        return 0.0
    try:
        data["bin"] = pd.qcut(data[factor_col], bins, duplicates="drop", labels=False)
    except ValueError:
        return 0.0
    iv = 0.0
    for b in data["bin"].unique():
        mask = data["bin"] == b
        good = data.loc[mask, target_col].sum()
        bad = mask.sum() - good
        total_good = data[target_col].sum()
        total_bad = len(data) - total_good
        if total_good == 0 or total_bad == 0:
            continue
        good_pct = good / total_good if total_good > 0 else 0.001
        bad_pct = bad / total_bad if total_bad > 0 else 0.001
        good_pct = max(good_pct, 0.001)
        bad_pct = max(bad_pct, 0.001)
        woe = np.log(good_pct / bad_pct)
        iv += (good_pct - bad_pct) * woe
    return round(float(iv), 4)

def compute_psi(panel: pd.DataFrame, factor_col: str, bins: int = None) -> float:
    """计算 PSI（三段时间等分，以早期为基准）。panel 已按时序排列。"""
    if bins is None:
        bins = N_BINS_IV
    data = panel[[factor_col]].dropna()
    n = len(data)
    if n < 100:
        return 0.0
    chunk = n // PSI_SPLITS
    base_data = data.iloc[:chunk][factor_col]
    try:
        base_bins = pd.qcut(base_data, bins, duplicates="drop", retbins=True)[1]
    except ValueError:
        return 0.0
    
    psi_total = 0.0
    for i in range(1, PSI_SPLITS):
        actual = data.iloc[i*chunk:(i+1)*chunk][factor_col]
        base_dist = pd.cut(base_data, bins=base_bins, include_lowest=True).value_counts(normalize=True).sort_index()
        actual_dist = pd.cut(actual, bins=base_bins, include_lowest=True).value_counts(normalize=True).sort_index()
        base_dist = base_dist.reindex(actual_dist.index, fill_value=0.001)
        actual_dist = actual_dist.clip(lower=0.001)
        psi = ((actual_dist - base_dist) * np.log(actual_dist / base_dist)).sum()
        psi_total += psi
    return round(float(psi_total / (PSI_SPLITS - 1)), 4)

def compute_ic(panel: pd.DataFrame, factor_col: str, target_col: str = "target") -> float:
    """Spearman IC: 因子值 vs 目标（内置实现，无外部依赖）。"""
    data = panel[[factor_col, target_col]].dropna()
    if len(data) < 30:
        return 0.0
    # Spearman = Pearson on ranks (manual fallback if scipy absent)
    try:
        from scipy.stats import spearmanr
        corr, _ = spearmanr(data[factor_col], data[target_col])
    except (ImportError, ModuleNotFoundError):
        x_rank = data[factor_col].rank()
        y_rank = data[target_col].rank()
        corr = x_rank.corr(y_rank)
    return round(float(corr), 4)

def compute_correlation_matrix(panel: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
    """因子间 Pearson r 矩阵。"""
    return panel[factor_cols].corr()

def analyze_panel(panel: pd.DataFrame, stock_mode: bool = False) -> dict:
    """对整个面板运行完整分析。stock_mode=True 时用5箱分箱+放宽PSI。"""
    factor_cols = [c for c in FACTOR_NAMES if c in panel.columns]
    if not factor_cols:
        return {"error": "面板无有效因子列"}
    
    # 个股模式：5箱（每箱~16点，比10箱的~8点更稳）
    bins = 5 if stock_mode else N_BINS_IV
    
    # 样本量
    n_rows = len(panel.dropna(subset=factor_cols + ["target"]))
    
    # 逐个因子算 IV / PSI / IC
    rankings = []
    for fc in factor_cols:
        iv = compute_iv(panel, fc, bins=bins)
        psi = compute_psi(panel, fc, bins=bins)
        ic = compute_ic(panel, fc)
        
        # 方向判定
        data = panel[[fc, "target"]].dropna()
        if len(data) > 30:
            high_mask = data[fc] > data[fc].median()
            high_win = data.loc[high_mask, "target"].mean()
            low_win = data.loc[~high_mask, "target"].mean()
            direction = "正向（因子值越高→涨的概率越高）" if high_win > low_win else "反向（因子值越高→跌的概率越高）"
        else:
            direction = "数据不足"
        
        # 综合评级
        if iv >= 0.1 and psi < 0.1 and abs(ic) > 0.05:
            grade = "★★★★★ 强有效"
        elif iv >= 0.02 and psi < 0.25 and abs(ic) > 0.03:
            grade = "★★★ 有效"
        elif iv >= 0.02 and psi >= 0.25:
            grade = "★★ 有效但不稳定"
        elif iv < 0.02:
            grade = "★ 弱" if psi < 0.25 else "淘汰"
        else:
            grade = "★★ 有效但不稳定"
        
        rankings.append({
            "factor": fc,
            "name": FACTOR_NAMES.get(fc, fc),
            "iv": iv,
            "psi": psi,
            "ic": ic,
            "grade": grade,
            "direction": direction,
        })
    
    rankings.sort(key=lambda x: x["iv"], reverse=True)
    
    # 相关性去重
    corr_matrix = compute_correlation_matrix(panel, factor_cols)
    warnings = []
    removed = set()
    
    # 个股模式：PSI 过高的因子先标记为"已淘汰"，不能参与去重（防止它误杀 PSI 合格的因子）
    if stock_mode:
        psi_limit = 0.45
        for r in rankings:
            if r["psi"] >= psi_limit:
                removed.add(r["factor"])
    
    for i in range(len(factor_cols)):
        for j in range(i+1, len(factor_cols)):
            fi, fj = factor_cols[i], factor_cols[j]
            # 已被预淘汰的因子不参与去重
            if fi in removed or fj in removed:
                continue
            r = corr_matrix.iloc[i, j]
            if abs(r) >= CORR_THRESHOLD:
                fi, fj = factor_cols[i], factor_cols[j]
                ivi = next(rr["iv"] for rr in rankings if rr["factor"] == fi)
                ivj = next(rr["iv"] for rr in rankings if rr["factor"] == fj)
                keep, drop = (fi, fj) if ivi >= ivj else (fj, fi)
                if drop not in removed:
                    warnings.append({
                        "pair": [fi, fj],
                        "r": round(float(r), 3),
                        "action": f"去 {drop}（IV={min(ivi,ivj)} 低于 {keep} IV={max(ivi,ivj)}）"
                    })
                    removed.add(drop)
    
    # 稳定性告警
    alerts = []
    for r in rankings:
        if r["psi"] >= 0.25:
            alerts.append({
                "factor": r["factor"],
                "psi": r["psi"],
                "message": f"{r['name']} PSI={r['psi']}≥0.25，近期分布与早期显著不同，因子可能失效"
            })
    
    # 三套有效因子方案
    def _build_scheme(name: str, iv_min: float, psi_max: float, 
                      removed_set: set, rankings: list) -> dict:
        """按条件筛选+去重，输出一套方案。"""
        candidates = [r for r in rankings 
                      if r["factor"] not in removed_set 
                      and r["iv"] >= iv_min 
                      and r["psi"] < psi_max]
        return {
            "scheme": name,
            "factors": [c["factor"] for c in candidates],
            "count": len(candidates),
            "avg_iv": round(np.mean([c["iv"] for c in candidates]), 4) if candidates else 0,
            "avg_psi": round(np.mean([c["psi"] for c in candidates]), 4) if candidates else 0,
            "avg_ic": round(np.mean([abs(c["ic"]) for c in candidates]), 4) if candidates else 0,
        }
    
    # 三套有效因子方案（个股放宽 PSI）
    psi_r = 0.45 if stock_mode else 0.25  # 去冗余 PSI
    psi_s = 0.45 if stock_mode else 0.25  # 高区分 PSI
    psi_st = 0.25 if stock_mode else 0.10 # 稳定优先 PSI
    
    effective_sets = {
        "去冗余":   _build_scheme(f"去冗余（IV≥0.02, PSI<{psi_r}, |r|<0.7）", 0.02, psi_r, removed, rankings),
        "高区分":   _build_scheme(f"高区分（IV≥0.10, PSI<{psi_s}, |r|<0.7）", 0.10, psi_s, removed, rankings),
        "稳定优先": _build_scheme(f"稳定优先（IV≥0.01, PSI<{psi_st}, |r|<0.7）", 0.01, psi_st, removed, rankings),
    }
    
    return {
        "n_rows": n_rows,
        "factor_ranking": rankings,
        "correlation_warnings": warnings,
        "stability_alerts": alerts,
        "effective_sets": effective_sets,
    }


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def update_panel(index_name: str, batch_size: int = 100) -> Optional[dict]:
    """更新单个指数面板。超百只自动分批拉K线（每批100只），合并后一次性分析。"""
    print(f"[{index_name}] 拉成分股…")
    try:
        codes = get_index_constituents(index_name)
    except Exception as e:
        print(f"[{index_name}] 成分股获取失败: {e}")
        return None
    
    n_total = len(codes)
    n_use = n_total
    
    # 分批拉K线（不受 SAMPLE_LIMIT 影响，样本数决定最终统计质量）
    if n_total > SAMPLE_LIMIT:
        rng = random.Random(hashlib.md5(datetime.now().strftime("%Y%m%d").encode()).hexdigest())
        codes = rng.sample(codes, SAMPLE_LIMIT)
        n_use = SAMPLE_LIMIT
        print(f"[{index_name}] {n_total}只→抽{SAMPLE_LIMIT}只用于分析")
    else:
        print(f"[{index_name}] {n_total}只全量")
    
    # 分批拉取（每批 ≤ batch_size，不掉数据）
    klines = {}
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(codes) + batch_size - 1) // batch_size
        print(f"[{index_name}] 拉K线 批次{batch_num}/{total_batches} ({len(batch)}只)…")
        batch_klines = fetch_klines_parallel(batch)
        klines.update(batch_klines)
        print(f"[{index_name}]   批次{batch_num}: {len(batch_klines)}/{len(batch)} 有效 (累计 {len(klines)})")
    
    print(f"[{index_name}] K线获取: {len(klines)}/{len(codes)} 只有效")
    
    if len(klines) < 15:
        print(f"[{index_name}] 有效股票<15只，跳过")
        return None
    
    print(f"[{index_name}] 构建面板…")
    panel = build_panel(klines)
    if len(panel) < MIN_SAMPLES:
        print(f"[{index_name}] 面板行数({len(panel)})<{MIN_SAMPLES}，跳过")
        return None
    
    print(f"[{index_name}] 分析中… 面板 {len(panel)} 行")
    analysis = analyze_panel(panel)
    
    # 提取数据覆盖范围
    if "date" in panel.columns:
        dates = pd.to_datetime(panel["date"])
        data_start = dates.min().strftime("%Y-%m-%d")
        data_end   = dates.max().strftime("%Y-%m-%d")
        data_range = f"{data_start} ~ {data_end}"
    else:
        data_range = "未知"
    
    result = {
        "meta": {
            "index": index_name,
            "index_code": INDEX_DEFS[index_name]["code"],
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "data_range": data_range,
            "lookback_days": LOOKBACK,
            "forward_days": FORWARD,
            "stock_count_total": n_total,
            "stock_count_used": len(klines),
            "valid_rows": len(panel),
            "sampled": n_total > SAMPLE_LIMIT,
        },
        **analysis,
        "summary": _make_summary(index_name, analysis),
    }
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = PANELS_DIR / f"{index_name}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[{index_name}] ✅ 写入 {out_path} ({os.path.getsize(out_path)} bytes)")
    
    # 同步更新全局 meta
    _sync_meta()
    return result

def _sync_meta():
    """同步全局 meta 文件。汇总所有面板的历史版本，标出各指数最新文件。"""
    from collections import defaultdict
    
    panels_by_index = defaultdict(list)
    for f in sorted(PANELS_DIR.glob("*.json")):
        if f.name == "_meta.json":
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            index_name = d["meta"]["index"]
            panels_by_index[index_name].append({
                "file": f.name,
                "generated_at": d["meta"]["generated_at"],
                "data_range": d["meta"].get("data_range", "未知"),
                "stock_count": d["meta"]["stock_count_used"],
            })
        except Exception:
            pass
    
    latest = {}
    for name, versions in panels_by_index.items():
        versions.sort(key=lambda x: x["generated_at"], reverse=True)
        latest[name] = versions[0]["file"]
    
    meta = {
        "synced_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "latest": latest,
        "history": {name: vs for name, vs in panels_by_index.items()},
    }
    with open(PANELS_DIR / "_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def _make_summary(index_name: str, analysis: dict) -> str:
    """生成人类可读摘要。"""
    sets = analysis.get("effective_sets", {})
    parts = []
    for name, s in sets.items():
        parts.append(f"{name}={s['count']}个")
    top3 = [r["name"] for r in analysis.get("factor_ranking", [])[:3]]
    return f"{index_name}：{' / '.join(parts)}，Top3={top3}"

def update_all_panels():
    """更新所有指数面板。"""
    for name in INDEX_DEFS:
        try:
            update_panel(name)
        except Exception as e:
            print(f"[{name}] 失败: {e}")
        time.sleep(random.uniform(2, 5))
    print("全部面板更新完成 ✅")

def get_stock_quality(code: str, force: bool = False) -> Optional[dict]:
    """获取/缓存个股因子质量（惰性）。"""
    cache_path = STOCKS_DIR / f"{code}.json"
    
    if not force and cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = (datetime.now() - mtime).days
        if age <= 30:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached["_cache_age_days"] = age
            return cached
        elif age <= 90:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached["_cache_age_days"] = age
            cached["_stale_warning"] = f"缓存已{age}天，建议刷新"
            return cached
    
    # 拉K线 + 计算
    print(f"[{code}] 拉K线…")
    df = fetch_kline(code)
    if df is None:
        return None
    
    print(f"[{code}] 计算因子…")
    factors = compute_all_factors(df)
    close = df["close"].astype(float)
    fwd_return = close.shift(-FORWARD) / close - 1
    target = (fwd_return > 0).astype(int)
    
    panel = pd.DataFrame({"target": target})
    for col in factors.columns:
        panel[col] = factors[col].values
    panel = panel.dropna(subset=["target"])
    
    analysis = analyze_panel(panel, stock_mode=True)
    
    # 数据覆盖范围
    if "date" in df.columns:
        dates = pd.to_datetime(df["date"])
        data_range = f"{dates.min().strftime('%Y-%m-%d')} ~ {dates.max().strftime('%Y-%m-%d')}"
    else:
        data_range = "未知"
    
    result = {
        "meta": {
            "code": code,
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "data_range": data_range,
            "lookback_days": LOOKBACK,
            "forward_days": FORWARD,
            "valid_rows": len(panel),
        },
        **analysis,
        "summary": _make_summary(code, analysis),
    }
    
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[{code}] ✅ 写入 {cache_path}")
    return result


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="A股因子质量分析引擎 v0.1")
    parser.add_argument("--update-panels", action="store_true", help="更新全部指数面板")
    parser.add_argument("--panel", type=str, help="更新指定指数面板（如 沪深300）")
    parser.add_argument("--stock", type=str, help="获取个股因子质量（如 600519）")
    parser.add_argument("--force", action="store_true", help="强制重跑忽略缓存")
    args = parser.parse_args()
    
    if args.update_panels:
        update_all_panels()
    elif args.panel:
        if args.panel not in INDEX_DEFS:
            print(f"未知指数: {args.panel}，可选: {list(INDEX_DEFS.keys())}")
            sys.exit(1)
        update_panel(args.panel)
    elif args.stock:
        result = get_stock_quality(args.stock, force=args.force)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"无法获取 {args.stock} 的数据")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
