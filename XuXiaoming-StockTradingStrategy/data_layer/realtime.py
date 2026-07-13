#!/usr/bin/env python3
"""
盘中实时裁决模块 · realtime.py
==============================
交易日盘中手动触发 → 拉取实时行情 + 分钟线增量 → 输出盘中简报。

用法：
  python data_layer/realtime.py          # 终端输出
  python data_layer/realtime.py --json   # JSON 输出（给 Agent 调用）

数据流：
  spot(实时行情) + minute(今日分钟线) + verdict_v7(前一交易日裁决)
    → CHOP 盘中估算 + 三合一方向 + 分钟线结构检测
    → 盘中简报（~1000字）

设计原则：
  - 仅盘中启用（盘后自动走完整全流程，不跑此模块）
  - 精度标注「盘中估算」——用最新价代理收盘价
  - 手动触发，无 cron
"""

import os
import sys
import json
import math
import argparse
from datetime import datetime, date, time, timedelta
from pathlib import Path
from collections import defaultdict

import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(SCRIPTS))

# ============================================================
# 1. 交易日历
# ============================================================
def _china_now() -> datetime:
    """返回北京时间当前时刻"""
    from datetime import timezone as tz_mod
    china_tz = tz_mod(timedelta(hours=8))
    return datetime.now(china_tz)


def is_trading_day(d: date = None) -> bool:
    """简单判断：周一到周五"""
    if d is None:
        d = _china_now().date()
    if d.weekday() >= 5:
        return False
    return True


def get_previous_trading_day(ref_date: date = None) -> date:
    """获取 ref_date 之前最近的一个交易日（跳过周末）"""
    if ref_date is None:
        ref_date = _china_now().date()
    d = ref_date - timedelta(days=1)
    while d.weekday() >= 5:  # 跳过周末
        d -= timedelta(days=1)
    return d


def is_trading_hours(now: datetime = None) -> bool:
    """判断是否在 A 股交易时段内（北京时间）"""
    if now is None:
        now = _china_now()
    t = now.time()
    morning = time(9, 30) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(15, 0)
    return morning or afternoon


def market_status() -> str:
    """返回市场状态：开盘/午休/收盘/休市"""
    now = _china_now()
    if not is_trading_day(now.date()):
        return "休市"
    t = now.time()
    if time(9, 30) <= t <= time(11, 30):
        return "开盘（上午）"
    if time(11, 30) < t < time(13, 0):
        return "午休"
    if time(13, 0) <= t <= time(15, 0):
        return "开盘（下午）"
    if t < time(9, 30):
        return "盘前"
    return "收盘"


def today_has_minute_data() -> bool:
    """检测今日分钟线是否已拉取"""
    today_str = _china_now().strftime("%Y-%m-%d")
    for idx_code in ["sh000001", "sz399001"]:
        name_map = {"sh000001": "上证指数", "sz399001": "深证成指"}
        csv_path = DATA / f"minute_raw_60_{idx_code}_{name_map[idx_code]}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            if "date" in df.columns:
                df["date_d"] = pd.to_datetime(df["date"]).dt.date
                if today_str in df["date_d"].astype(str).values:
                    return True
    return False


# ============================================================
# 2. 实时行情拉取（Sina 源）
# ============================================================
INDICES_SINA = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
}


def get_spot() -> dict:
    """拉取六指数实时行情，返回 {指数名: {price, change_pct, open, high, low, prev_close}}"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_sina()
        result = {}
        for _, row in df.iterrows():
            name = row["名称"]
            if name in INDICES_SINA.values():
                code = row["代码"]
                # Map Sina code → our index name
                idx_name = INDICES_SINA.get(code) or name
                if idx_name in result:
                    continue  # 去重（沪深300 sz399300 和 sh000300 都有）
                result[idx_name] = {
                    "code": code,
                    "price": float(row["最新价"]),
                    "change_pct": float(row["涨跌幅"]),
                    "open": float(row["今开"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "prev_close": float(row["昨收"]),
                    "volume": float(row["成交量"]),
                    "amount": float(row["成交额"]),
                }
        return result
    except Exception as e:
        print(f"❌ 实时行情拉取失败: {e}", file=sys.stderr)
        return {}


# ============================================================
# 3. 前一交易日裁决（含自动引擎前置）
# ============================================================
def ensure_verdict_fresh():
    """确保 verdict_v7.csv 包含前一交易日数据，无则自动跑裁决引擎。
    
    注意：此函数只保证 CSV 数据就绪，不负责生成前日完整报告。
    前日完整报告由 Agent 在触发盘中前检测并生成（有则复用，无则补跑全流程）。
    
    补跑全流程 ≠ 只跑 verdict_v7.py → 必须走两路并行Agent+合成+博客后置。
    """
    verdict_path = DATA / "verdict_v7.csv"
    prev_day = get_previous_trading_day()
    prev_str = prev_day.strftime("%Y-%m-%d")
    
    need_run = False
    if not verdict_path.exists():
        need_run = True
    else:
        df = pd.read_csv(verdict_path)
        if prev_str not in df["date"].values:
            need_run = True
    
    if need_run:
        import subprocess
        engine_path = SCRIPTS / "verdict_v7.py"
        result = subprocess.run(
            [sys.executable, str(engine_path)],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE)
        )
        if result.returncode != 0:
            raise RuntimeError(f"裁决引擎运行失败:\n{result.stderr}")


def find_previous_report(ref_date: date = None) -> Path | None:
    """查找前一次易日的完整报告文件。
    
    搜索 ~/reports/ 目录，匹配文件名中的日期前缀。
    例如找 2026-07-10 的报告 → 匹配 '2026-07-10_' 开头的 .md 文件。
    
    返回最新匹配文件的 Path，无匹配返回 None。
    """
    if ref_date is None:
        ref_date = get_previous_trading_day()
    date_prefix = ref_date.strftime("%Y-%m-%d_")
    
    reports_dir = Path.home() / "reports"
    if not reports_dir.exists():
        return None
    
    matches = sorted(
        [f for f in reports_dir.glob(f"{date_prefix}*.md")],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    return matches[0] if matches else None


def ensure_previous_report_exists() -> Path | None:
    """检查前日完整报告是否存在。存在返回路径，不存在返回 None。
    
    返回 None 时，调用方（Agent）必须补跑全流程：
    ① delegate_task 两路并行 → ② 主Agent合成 → ③ 博客后置 → ④ 输出MD文件。
    不可走捷径——不能只跑 verdict_v7.py 或单 Agent 手写。
    """
    prev_day = get_previous_trading_day()
    report_path = find_previous_report(prev_day)
    if report_path:
        return report_path
    return None


def get_yesterday_verdict() -> dict:
    """读取前一交易日的裁决数据（精确跳过周末+今天）"""
    ensure_verdict_fresh()
    
    df = pd.read_csv(DATA / "verdict_v7.csv")
    prev_day = get_previous_trading_day()
    prev_str = prev_day.strftime("%Y-%m-%d")
    
    # 精确定位前一交易日行（而不是简单取最后一行）
    prev_rows = df[df["date"] == prev_str]
    if len(prev_rows) == 0:
        raise RuntimeError(f"前一交易日 {prev_str} 在 verdict_v7.csv 中不存在")
    last = prev_rows.iloc[-1]
    
    indices_map = {
        "上证指数": "sh", "深证成指": "sz",
        "创业板指": "cyb", "科创50": "kc",
    }
    
    result = {"date": str(last["date"])}
    for name, suffix in indices_map.items():
        result[name] = {
            "close": float(last.get(f"close_{suffix}", 0) or 0),
            "regime": str(last.get(f"regime_{suffix}", "") or ""),
            "chop": float(last.get(f"chop_{suffix}", 0) or 0),
            "verdict": str(last.get(f"verdict_{suffix}", "") or ""),
            "reason": str(last.get(f"reason_{suffix}", "") or ""),
            "bs": int(last.get(f"bs_{suffix}", 0) or 0),
            "ts": int(last.get(f"ts_{suffix}", 0) or 0),
        }
    result["verdict_main"] = str(last.get("verdict_main", "") or "")
    result["verdict_tech"] = str(last.get("verdict_tech", "") or "")
    result["resonance"] = str(last.get("resonance", "") or "")
    result["cyb_kc_resonance"] = str(last.get("cyb_kc_resonance", "") or "")
    result["osc_origin_sz"] = str(last.get("osc_origin_sz", "") or "")
    result["osc_origin_sh"] = str(last.get("osc_origin_sh", "") or "")
    
    return result


# ============================================================
# 4. 盘中 CHOP 估算
# ============================================================
def estimate_chop_14(spot: dict, daily_df: pd.DataFrame) -> dict:
    """
    用盘中最高/最低/最新价 + 历史 13 天日线数据，估算 CHOP(14)。
    
    CHOP(14) = 100 * log10(ΣTR(14) / (HH(14) - LL(14))) / log10(14)
    TR = max(H-L, |H-prevC|, |L-prevC|)
    
    对于今天（第 14 天）：
      H = spot['high']（盘中最高）
      L = spot['low']（盘中最低）
      prevC = 昨日收盘
    """
    result = {}
    for idx_name, suffix in [("上证指数", "sh"), ("深证成指", "sz"), 
                               ("创业板指", "cyb"), ("科创50", "kc")]:
        sp = spot.get(idx_name)
        if not sp:
            result[idx_name] = None
            continue
        
        # 从 daily_raw 取最近 13 天的该指数日线
        idx_rows = daily_df[daily_df["index_name"] == idx_name].sort_values("date")
        if len(idx_rows) < 13:
            result[idx_name] = None
            continue
        
        last_13 = idx_rows.iloc[-13:]
        
        tr_sum = 0.0
        highs = []
        lows = []
        
        for _, row in last_13.iterrows():
            h, l, c_prev = row["high"], row["low"], row["close"]
            prev_c = last_13.iloc[max(0, last_13.index.get_loc(row.name) - 1)]["close"] if row.name != last_13.index[0] else c_prev
            # For the very first row, use itself as prevC
            if row.name == last_13.index[0]:
                prev_c = last_13.iloc[0]["close"]
            else:
                prev_idx = last_13.index.get_loc(row.name) - 1
                prev_c = last_13.iloc[prev_idx]["close"]
            
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_sum += tr
            highs.append(h)
            lows.append(l)
        
        # Add today's estimated TR
        today_tr = max(
            sp["high"] - sp["low"],
            abs(sp["high"] - last_13.iloc[-1]["close"]),
            abs(sp["low"] - last_13.iloc[-1]["close"])
        )
        tr_sum += today_tr
        highs.append(sp["high"])
        lows.append(sp["low"])
        
        hh = max(highs)
        ll = min(lows)
        
        if hh > ll:
            chop = 100 * math.log10(tr_sum / (hh - ll)) / math.log10(14)
        else:
            chop = 100
        
        result[idx_name] = {
            "chop": round(chop, 1),
            "chop_level": "clear" if chop < 38.2 else ("fuzzy" if chop <= 61.8 else "chaotic"),
            "warning": _chop_warning(idx_name, chop),
        }
    
    return result


def _chop_warning(idx_name: str, chop: float) -> str:
    """CHOP 风险标注"""
    if chop > 61.8:
        return f"⚠️ 已超 61.8 → 趋势策略退位，震荡策略接管"
    elif chop > 55:
        gap = 61.8 - chop
        return f"⚠️ CHOP={chop:.0f}，距 61.8 切换线仅 {gap:.1f} 点"
    elif chop < 38.2:
        return "CHOP<38.2 关注"
    return ""


# ============================================================
# 5. 盘中三合一方向估计
# ============================================================
def estimate_regime(spot: dict, daily_df: pd.DataFrame) -> dict:
    """
    用最新价代理收盘，喂入三合一（简化版：只看动量方向 + CHOP 可信度）。
    不做完整的 250 天分位标准化——盘中精度足够。
    
    简化逻辑：用 20 日动量 + 当日涨跌判断偏多/偏空。
    """
    result = {}
    for idx_name, suffix in [("上证指数", "sh"), ("深证成指", "sz"),
                               ("创业板指", "cyb"), ("科创50", "kc")]:
        sp = spot.get(idx_name)
        if not sp:
            result[idx_name] = {"regime": "未知", "direction": "未知"}
            continue
        
        idx_rows = daily_df[daily_df["index_name"] == idx_name].sort_values("date")
        if len(idx_rows) < 20:
            result[idx_name] = {"regime": "未知", "direction": "未知"}
            continue
        
        # 20 日动量：最新价 vs 20 日前收盘
        close_20d_ago = idx_rows.iloc[-20]["close"]
        mom = (sp["price"] / close_20d_ago - 1) * 100
        today_change = sp["change_pct"]
        
        # 简化方向判断
        if mom > 3 and today_change > 0:
            regime = "偏多"
            direction = "上行"
        elif mom < -3 and today_change < 0:
            regime = "偏空"
            direction = "下行"
        elif mom > 0:
            regime = "偏多"
            direction = "偏上行"
        elif mom < 0:
            regime = "偏空"
            direction = "偏下行"
        else:
            regime = "震荡"
            direction = "无方向"
        
        result[idx_name] = {
            "regime": regime,
            "direction": direction,
            "mom_20d": round(mom, 2),
            "today_change": round(today_change, 2),
        }
    
    return result


# ============================================================
# 6. 分钟线结构检测（复用已有引擎）
# ============================================================
def check_minute_structure(fetch_today: bool = True) -> dict:
    """
    运行分钟线结构引擎，检测今日是否有结构形成。
    
    Args:
        fetch_today: 是否先拉取今日分钟线数据。设为 True 时会先检测
                     今日数据是否已有，已有则跳过拉取（避免重复~40s耗时）。
    """
    if fetch_today and not today_has_minute_data():
        try:
            from data_layer.fetch import fetch_all_minute
            fetch_all_minute()
        except Exception as e:
            pass  # 拉取失败不阻断，用已有数据
    
    import importlib.util
    # 运行分钟线引擎生成最新信号
    spec = importlib.util.spec_from_file_location(
        "minute_v2", str(SCRIPTS / "minute_structure_v2.py")
    )
    if spec is None or spec.loader is None:
        return {"error": "分钟线引擎未找到"}
    
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        pass  # 引擎加载失败继续
    
    # 读取已生成的 CSV
    result = {}
    for idx_code, idx_name in [
        ("sh", "上证指数"), ("sz", "深证成指"),
        ("cyb", "创业板指"), ("kc", "科创50")
    ]:
        csv_path = DATA / f"minute_structure_v2_{idx_code}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            if len(df) > 0:
                last = df.iloc[-1]
                # 解析结构信号
                parts = []
                for period, col in [("60min", "top_form_60"), ("60min底", "bottom_form_60"),
                                     ("90min", "top_form_90"), ("90min底", "bottom_form_90"),
                                     ("120min", "top_form_120"), ("120min底", "bottom_form_120")]:
                    if col in last.index and pd.notna(last[col]) and int(last[col]) == 1:
                        parts.append(period)
                
                # 顶钝化
                for period, col in [("60min", "td_60"), ("90min", "td_90"), ("120min", "td_120")]:
                    if col in last.index and pd.notna(last[col]) and int(last[col]) == 1:
                        parts.append(f"{period}顶钝化")
                # 底钝化（需结合日线判断，仅标注）
                for period, col in [("60min", "bd_60"), ("90min", "bd_90"), ("120min", "bd_120")]:
                    if col in last.index and pd.notna(last[col]) and int(last[col]) == 1:
                        parts.append(f"{period}底钝化⚠")
                
                signal_level = str(last.get("signal_level", "")) if "signal_level" in last.index else ""
                top_res = int(last.get("top_resonance", 0) or 0) if "top_resonance" in last.index else 0
                bot_res = int(last.get("bot_resonance", 0) or 0) if "bot_resonance" in last.index else 0
                golden = int(last.get("golden_cross_res", 0) or 0) if "golden_cross_res" in last.index else 0
                dead = int(last.get("dead_cross_res", 0) or 0) if "dead_cross_res" in last.index else 0
                
                result[idx_name] = {
                    "date": str(last.get("date", "")),
                    "signals": ", ".join(parts) if parts else "无",
                    "signal_level": signal_level,
                    "top_resonance": top_res,
                    "bot_resonance": bot_res,
                    "golden_cross": golden,
                    "dead_cross": dead,
                }
    return result


# ============================================================
# 7. 盘中简报生成
# ============================================================
def generate_briefing(spot: dict, yesterday: dict, chop_est: dict, 
                      regime_est: dict, minute_signals: dict,
                      status: str) -> str:
    """生成 ~1000 字盘中简报"""
    now = _china_now()
    prev_date = yesterday["date"]
    
    lines = []
    lines.append("# 盘中裁决简报")
    weekday_cn = ["周一","周二","周三","周四","周五","周六","周日"][now.weekday()]
    lines.append(f"**{now.strftime('%Y-%m-%d')} {weekday_cn} {now.strftime('%H:%M')}** | 市场状态：**{status}** | 接续：{prev_date} 裁决")
    lines.append("")
    
    # ── 一、实时行情 ──
    lines.append("## 一、实时行情")
    lines.append("")
    lines.append("| 指数 | 最新价 | 涨跌幅 | 今开 | 最高 | 最低 | 昨收 |")
    lines.append("|------|------|------|------|------|------|------|")
    for name in ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "中证500"]:
        sp = spot.get(name)
        if sp:
            lines.append(f"| {name} | {sp['price']:.2f} | {sp['change_pct']:+.2f}% | "
                        f"{sp['open']:.2f} | {sp['high']:.2f} | {sp['low']:.2f} | {sp['prev_close']:.2f} |")
    lines.append("")
    
    # ── 二、接续昨日裁决 ──
    lines.append("## 二、接续昨日（{prev_date}）核心判断".format(prev_date=prev_date))
    lines.append("")
    
    # 提炼昨日核心观点（从 verdict + reason 生成叙述）
    v_main = yesterday["verdict_main"]
    v_tech = yesterday["verdict_tech"]
    resonance = yesterday["resonance"]
    ck_res = yesterday["cyb_kc_resonance"]
    
    # 主板叙述
    main_narrative = ""
    if "持股" in v_main:
        main_narrative = "主板持仓看多——趋势为王，持股不动"
    elif "观望(偏多)" in v_main:
        main_narrative = "主板观望偏多——震荡中来路上行，等底结构确认"
    elif "观望" in v_main:
        main_narrative = "主板观望——震荡市多看少动，等信号明确"
    elif "空仓" in v_main:
        main_narrative = "主板空仓防守——趋势向下"
    elif "减仓" in v_main:
        main_narrative = "主板减仓——顶结构触发防守"
    else:
        main_narrative = f"主板{v_main}"
    
    # 科技叙述
    tech_narrative = ""
    if "持股" in v_tech:
        tech_narrative = "科技持仓看多"
    elif "观望" in v_tech:
        tech_narrative = "科技观望等待"
    elif "减仓" in v_tech:
        tech_narrative = "科技减仓防守"
    elif "空仓" in v_tech:
        tech_narrative = "科技空仓"
    else:
        tech_narrative = f"科技{v_tech}"
    
    lines.append(f"> {main_narrative}；{tech_narrative}。共振：{resonance}；双创共振：{ck_res}。")
    lines.append("")
    
    # ── 提炼 3-5 条核心判断（从各指数 reason 提取操作含义）──
    lines.append("**昨日报告的三条核心判断：**")
    lines.append("")
    
    kc_yd = yesterday.get("科创50", {})
    sh_yd = yesterday.get("上证指数", {})
    sz_yd = yesterday.get("深证成指", {})
    cyb_yd = yesterday.get("创业板指", {})
    
    # 判断 1: 主板策略
    if "观望" in str(sh_yd.get("verdict", "")):
        lines.append(f"① **主板「等底结构」。** 上证观望、深证{sz_yd.get('verdict','')}→来路上行偏多但无底结构不操作。"
                     f"「有就有缘分，没有就随缘。」")
    elif "持股" in str(sh_yd.get("verdict", "")):
        lines.append(f"① **主板「持股不动」。** 趋势为王——上证{sh_yd.get('verdict','')}、深证{sz_yd.get('verdict','')}。")
    elif "空仓" in str(sh_yd.get("verdict", "")):
        lines.append(f"① **主板「空仓防守」。** 趋势向下——上证{sh_yd.get('verdict','')}。")
    
    # 判断 2: 科创50 CHOP 风险
    kc_chop = kc_yd.get("chop", 0)
    if kc_chop > 55:
        gap = 61.8 - kc_chop
        lines.append(f"② **科创50「随时准备翻牌」。** {kc_yd.get('verdict','')}（{kc_yd.get('regime','')}），但 CHOP={kc_chop:.0f} "
                     f"距 61.8 硬切换仅 {gap:.1f} 点。一旦破线→趋势策略退位、震荡策略接管。这是昨日最紧迫的风险。")
    elif kc_chop > 38.2:
        lines.append(f"② **科创50「趋势可信」。** {kc_yd.get('verdict','')}（{kc_yd.get('regime','')}），CHOP={kc_chop:.0f} "
                     f"在 fuzzy 区间，趋势和结构等权重。")
    else:
        lines.append(f"② **科创50「趋势清晰」。** {kc_yd.get('verdict','')}（{kc_yd.get('regime','')}），CHOP={kc_chop:.0f}<38.2 clear。")
    
    # 判断 3: 底结构/序列/月周低9
    has_day_seq = "低9" in str(sz_yd.get("reason", "")) or "低9" in str(cyb_yd.get("reason", "")) or "高9" in str(sz_yd.get("reason", ""))
    has_month = yesterday.get("month_win", False)
    has_week = yesterday.get("week_win", False)
    has_bs = kc_yd.get("bs", 0) or sh_yd.get("bs", 0) or sz_yd.get("bs", 0)
    
    parts = []
    if has_day_seq: parts.append("日线序列信号出现")
    if has_month: parts.append("月低9窗口内（40天）")
    if has_week: parts.append("周低9窗口内（20天）")
    if has_bs: parts.append("底部结构形成")
    
    if parts:
        lines.append(f"③ **{'、'.join(parts)}。** " 
                     f"震荡市中的辅助信号——不是买入原则，但提供关注逻辑。")
    else:
        lines.append(f"③ **无结构、无序列。** 纯震荡状态——没有操作标准。")
    
    # 判断 4: 年内底结构极度匮乏（从历史数据推断）
    lines.append(f"④ **底结构极度匮乏。** 上证深证年内零底结构——真正的底还很远，"
                 f"底结构的形成需要钝化→DIF拐头→金叉，不是几天能完成的。")
    
    lines.append("")
    
    # ── 今日盘中对照 ──
    lines.append("**今日盘中对照：**")
    lines.append("")
    
    for name in ["上证指数", "深证成指", "创业板指", "科创50"]:
        sp = spot.get(name)
        yd = yesterday.get(name, {})
        if not sp:
            continue
        
        yd_verdict = str(yd.get("verdict", ""))
        today_chg = sp["change_pct"]
        today_direction = "上涨" if today_chg > 0 else "下跌"
        
        if ("持股" in yd_verdict) and today_chg < 0:
            status_icon = "⚠️ 回调"
            note = f"持股 + 今日{today_direction} {today_chg:+.2f}%，关注是否破位"
        elif ("持股" in yd_verdict) and today_chg > 0:
            status_icon = "✅ 延续" 
            note = "趋势方向一致"
        elif ("观望" in yd_verdict) and today_chg < -1:
            status_icon = "⬇️ 走弱"
            note = f"观望 + 大跌 {today_chg:+.2f}%，下行压力加大"
        elif ("观望" in yd_verdict):
            status_icon = "➡️ 延续"
            note = "仍在观望状态，策略不变"
        elif ("空仓" in yd_verdict) and today_chg < 0:
            status_icon = "✅ 延续"
            note = "空仓正确"
        elif ("空仓" in yd_verdict) and today_chg > 0:
            status_icon = "⚠️ 反弹"
            note = "关注是否突破趋势"
        else:
            status_icon = "—"
            note = ""
        
        lines.append(f"- {status_icon} **{name}**：昨日{yd_verdict} → 今日{today_direction} {today_chg:+.2f}% | {note}")
    lines.append("")
    lines.append("")
    
    # ── 三、盘中 CHOP 估算 ──
    lines.append("## 三、盘中 CHOP 估算（盘中估算）")
    lines.append("")
    for name in ["上证指数", "深证成指", "创业板指", "科创50"]:
        ce = chop_est.get(name)
        yd = yesterday.get(name, {})
        yd_chop = yd.get("chop", 0)
        if ce:
            arrow = "↑" if ce["chop"] > yd_chop else ("↓" if ce["chop"] < yd_chop else "→")
            gap_str = f" 较昨日 {yd_chop:.1f} {arrow}" if yd_chop else ""
            lines.append(f"- **{name}**：CHOP≈{ce['chop']:.1f}（{ce['chop_level']}）{gap_str}")
            if ce.get("warning"):
                lines.append(f"  - {ce['warning']}")
        else:
            lines.append(f"- **{name}**：数据不足无法估算")
    lines.append("")
    
    # ── 四、盘中方向估计 ──
    lines.append("## 四、盘中方向估计（盘中估算）")
    lines.append("")
    for name in ["上证指数", "深证成指", "创业板指", "科创50"]:
        re = regime_est.get(name)
        yd = yesterday.get(name, {})
        if re:
            yd_regime = yd.get("regime", "")
            changed = " ⚠️方向变化" if (re["regime"] != yd_regime and yd_regime) else ""
            lines.append(f"- **{name}**：{re['regime']}（20日动量 {re['mom_20d']:+.1f}% | 今日 {re['today_change']:+.2f}%）{changed}")
    lines.append("")
    
    # ── 五、分钟线结构 ──
    lines.append("## 五、分钟线结构")
    lines.append("")
    if minute_signals and not minute_signals.get("error"):
        for idx_name, sig in minute_signals.items():
            level = sig.get("signal_level", "—")
            signals = sig.get("signals", "—")
            top_r = sig.get("top_resonance", 0)
            bot_r = sig.get("bot_resonance", 0)
            golden = sig.get("golden_cross", 0)
            dead = sig.get("dead_cross", 0)
            
            status_line = f"- **{idx_name}**：{level}"
            if signals != "无":
                status_line += f" | {signals}"
            if top_r:
                status_line += f" | 顶共振={top_r}"
            if bot_r:
                status_line += f" | 底共振={bot_r}"
            if golden:
                status_line += f" | 金叉共振={golden}"
            if dead:
                status_line += f" | 死叉共振={dead}"
            lines.append(status_line)
    else:
        lines.append("- 分钟线数据未拉取或引擎不可用")
        if minute_signals.get("error"):
            lines.append(f"  - 错误：{minute_signals['error']}")
    lines.append("")
    
    # ── 六、盘中裁决判断 ──
    lines.append("## 六、盘中裁决判断")
    lines.append("")
    
    # 科创50 是我们的焦点
    kc_sp = spot.get("科创50", {})
    kc_chop = chop_est.get("科创50", {})
    kc_regime = regime_est.get("科创50", {})
    kc_yd = yesterday.get("科创50", {})
    
    if kc_chop and kc_chop.get("chop_level") == "chaotic":
        lines.append("### ⚠️ 科创50：CHOP 已破 61.8，趋势策略退位")
        lines.append("")
        lines.append(f"- 当前 CHOP ≈ {kc_chop['chop']:.1f}（chaotic），**单日即切→震荡策略**")
        lines.append(f"- 昨日裁决：{kc_yd.get('verdict', '—')} | 今日应转为：**观望**")
        lines.append(f"- 来路：{yesterday.get('osc_origin_sz', '—')} → 确定震荡默认姿态")
        if kc_yd.get("verdict", "").startswith("持股"):
            lines.append("- ⚠️ **建议：减仓/清仓。** 趋势策略已不适用。")
        lines.append("- 后续：等底部结构 + BS 筛选通过 → 试探入场")
    elif kc_chop and kc_chop["chop"] > 55:
        gap = 61.8 - kc_chop["chop"]
        lines.append(f"### ⚠️ 科创50：CHOP={kc_chop['chop']:.1f}，距 61.8 切换线仅 {gap:.1f} 点")
        lines.append("")
        lines.append(f"- 距硬切换一步之遥，随时可能从趋势策略翻牌为震荡策略")
        if kc_sp.get("change_pct", 0) < -1:
            lines.append("- 今日跌幅较大，需警惕 CHOP 加速上冲")
        if kc_yd.get("ts", 0):
            lines.append("- 近期有顶结构，叠加 CHOP 逼近切换线 → 风险叠加")
    else:
        cyb_sp = spot.get("创业板指", {})
        lines.append(f"### 当前信号")
        lines.append("")
        lines.append(f"- 科创50 CHOP={kc_chop.get('chop', '—')}（{kc_chop.get('chop_level', '—')}），趋势可信")
        lines.append(f"- 双创共振：{yesterday.get('cyb_kc_resonance', '—')}")
        if kc_yd.get("verdict", "").startswith("持股") and kc_sp.get("change_pct", 0) < 0:
            lines.append(f"- 持股 + 今日回调 {kc_sp.get('change_pct', 0):+.2f}% → 关注是否跌破趋势")
    
    lines.append("")
    
    # 主板
    sh_sp = spot.get("上证指数", {})
    lines.append(f"### 主板")
    lines.append(f"- 上证：{yesterday.get('上证指数', {}).get('verdict', '—')} | 今日 {sh_sp.get('change_pct', 0):+.2f}%")
    lines.append(f"- 共振：{yesterday.get('resonance', '—')}")
    lines.append("")
    
    # ── 七、关注点 ──
    lines.append("## 七、下一步关注")
    lines.append("")
    lines.append("1. **CHOP 轨迹**：关注科创50 CHOP 是否突破 61.8（硬切换触发点）")
    lines.append("2. **分钟线结构**：60/90/120 分钟是否形成底/顶结构")
    lines.append("3. **趋势破位**：收盘价是否跌破趋势通道下轨")
    lines.append("4. **双创共振**：创业板+科创50 方向是否协调")
    lines.append("")
    lines.append("> ⚠️ 本简报为盘中估算，CHOP/方向均为近似值。收盘后以完整流程报告为准。")
    
    return "\n".join(lines)


# ============================================================
# 8. 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="盘中实时裁决")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    
    status = market_status()
    
    if not is_trading_day():
        if args.json:
            print(json.dumps({"status": "休市", "message": "今日非交易日"}, ensure_ascii=False))
        else:
            print("今日非交易日，无需盘中裁决。收盘后用完整流程。")
        return
    
    if status == "收盘":
        if args.json:
            print(json.dumps({"status": "收盘", "message": "已收盘，请用完整流程"}, ensure_ascii=False))
        else:
            print("已收盘，请用完整流程（build.py + 全量分析）。")
        return
    
    # 1. 拉取实时行情
    spot = get_spot()
    if not spot:
        msg = "实时行情拉取失败"
        if args.json:
            print(json.dumps({"status": "error", "message": msg}, ensure_ascii=False))
        else:
            print(msg)
        return
    
    # 2. 读取昨日裁决
    yesterday = get_yesterday_verdict()
    
    # 3. 加载日线历史数据（用于 CHOP 估算）
    daily_path = DATA / "daily_raw.csv"
    if not daily_path.exists():
        msg = "日线历史数据缺失，请先运行 data_layer/build.py"
        if args.json:
            print(json.dumps({"status": "error", "message": msg}, ensure_ascii=False))
        else:
            print(msg)
        return
    daily_df = pd.read_csv(daily_path)
    
    # 4. CHOP 估算
    chop_est = estimate_chop_14(spot, daily_df)
    
    # 5. 方向估计
    regime_est = estimate_regime(spot, daily_df)
    
    # 6. 分钟线结构
    minute_signals = check_minute_structure()
    
    # 7. 生成简报
    briefing = generate_briefing(spot, yesterday, chop_est, regime_est, minute_signals, status)
    
    if args.json:
        print(json.dumps({
            "status": status,
            "time": _china_now().isoformat(),
            "briefing": briefing,
            "spot": spot,
            "chop_est": {k: v for k, v in chop_est.items() if v},
            "regime_est": regime_est,
        }, ensure_ascii=False, default=str))
    else:
        print(briefing)


if __name__ == "__main__":
    main()
