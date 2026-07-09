#!/usr/bin/env python3
"""
scorer.py — 多维度评分引擎

模式：
  --mode technical   → 择时分(-10~+10) + 趋势突破分(0~15) + 入场就绪度(0~10)
  --mode fundamental → 基本面分(0~25) ⚠️ 财务数据缺失时受限
  --mode full        → 全维度综合分(0~100) + 风控标记

输入：JSON (ta.py 输出 + 估值/财务数据)
输出：结构化评分

用法：
  python scorer.py --mode technical --input '<json>'
  python scorer.py --mode fundamental --input '<json>'
  python scorer.py --mode full --input '<json>'
"""

import json
import sys
import argparse


def score_technical(data: dict) -> dict:
    """技术面评分：择时分 + 趋势突破 + 入场就绪度。"""
    # 容错：裸 K 线数组或非预期格式 → 退化为中性评分
    if not isinstance(data, dict):
        return {"technical_timing": 0, "trend_breakout": 0, "entry_readiness": 0,
                "timing_detail": ["数据格式异常"], "trend_detail": [], "entry_detail": []}
    ta = data.get("ta", data)
    if isinstance(ta, list):  # 裸 K 线 → 无法做技术评分
        ta = {}
    multi = data.get("multi_tf", {})

    # ── 择时分 (-10 ~ +10) ──
    timing = 0
    timing_detail = []

    # MACD
    macd = ta.get("macd", {})
    if macd.get("signal") == "金叉买入":
        timing += 3
        timing_detail.append("MACD金叉 +3")
    elif macd.get("signal") == "死叉卖出":
        timing -= 3
        timing_detail.append("MACD死叉 -3")
    if macd.get("divergence") == "底背离":
        timing += 2
        timing_detail.append("底背离 +2")
    elif macd.get("divergence") == "顶背离":
        timing -= 2
        timing_detail.append("顶背离 -2")

    # MA 排列
    ma = ta.get("ma", {})
    if ma.get("arrangement") == "多头排列":
        timing += 2
        timing_detail.append("多头排列 +2")
    elif ma.get("arrangement") == "空头排列":
        timing -= 2
        timing_detail.append("空头排列 -2")

    # RSI
    rsi = ta.get("rsi", {})
    rsi_zone = rsi.get("zone", "正常")
    if rsi_zone == "严重超卖":
        timing += 1
        timing_detail.append("RSI严重超卖 +1(反转潜力)")
    elif rsi_zone == "严重超买":
        timing -= 1
        timing_detail.append("RSI严重超买 -1(回调风险)")

    # 布林带位置
    boll = ta.get("boll", {})
    boll_pos = boll.get("position", "")
    if boll_pos == "跌破下轨":
        timing += 1
        timing_detail.append("布林下轨 +1")
    elif boll_pos == "突破上轨":
        timing -= 1
        timing_detail.append("布林上轨 -1")

    # 布林带宽收窄 — 变盘前兆，方向取决于突破
    boll_bw = boll.get("bandwidth", "")
    if boll_bw == "极度收窄":
        timing += 0  # 本身中性，不加减分，但在入场就绪度加分
        timing_detail.append("布林极度收窄(变盘前兆)")

    # KDJ 极端区间 + 近期金叉/死叉检测
    kdj = ta.get("kdj", {})
    kdj_signal = kdj.get("signal", "")
    j_signal = kdj.get("J_signal", "")

    # 当前信号
    if kdj_signal == "低位金叉机会":
        timing += 2
        timing_detail.append("KDJ低位金叉 +2")
    elif kdj_signal == "高位死叉风险":
        timing -= 2
        timing_detail.append("KDJ高位死叉 -2")
    if j_signal == "超卖":
        timing += 1
        timing_detail.append("KDJ J值超卖 +1(反转潜力)")
    elif j_signal == "超买":
        timing -= 1
        timing_detail.append("KDJ J值超买 -1(回调风险)")

    # 近期极端 J 值修复检测（ta.py 只报当前状态，这里补历史）
    j_vals = [x for x in kdj.get("J", []) if x is not None]
    k_vals = [x for x in kdj.get("K", []) if x is not None]
    d_vals = [x for x in kdj.get("D", []) if x is not None]
    if len(j_vals) >= 5 and len(k_vals) >= 5 and len(d_vals) >= 5:
        j_recent5 = j_vals[-5:]
        k_recent5 = k_vals[-5:]
        d_recent5 = d_vals[-5:]
        j_min5 = min(j_recent5)
        j_now = j_recent5[-1]
        # 近期 J 曾极端超卖(<0)且已修复回正 → 底部反转信号
        if j_min5 < 0 and j_now > 0:
            timing += 1
            timing_detail.append(f"KDJ J曾跌至{j_min5:.0f}后修复 +1(底部反转)")
        # 近期 K 上穿 D（金叉已发生但 ta.py 未标注）
        cross_found = False
        for i in range(1, len(k_recent5)):
            if k_recent5[i-1] <= d_recent5[i-1] and k_recent5[i] > d_recent5[i]:
                cross_found = True
                break
        if cross_found and kdj_signal not in ("低位金叉机会", "高位死叉风险"):
            timing += 2
            timing_detail.append("KDJ近期金叉 +2")

    # 量价
    vol = ta.get("volume", {})
    vol_trend = vol.get("trend", "")
    if vol_trend == "放量上涨":
        timing += 2
        timing_detail.append("放量上涨 +2")
    elif vol_trend == "放量下跌":
        timing -= 2
        timing_detail.append("放量下跌 -2")
    elif "缩量上涨" in vol_trend:
        timing -= 1
        timing_detail.append("缩量上涨(背离) -1")

    # 多周期
    alignment = multi.get("alignment", "")
    if alignment == "一致看多":
        timing += 2
        timing_detail.append("多周期一致看多 +2")
    elif alignment == "一致看空":
        timing -= 2
        timing_detail.append("多周期一致看空 -2")
    elif alignment == "周期冲突":
        timing -= 1
        timing_detail.append("多周期冲突 -1")

    timing = max(-10, min(10, timing))

    # ── 趋势突破分 (0 ~ 15) ──
    trend_score = 5  # 基准
    trend_detail = []
    price = ta.get("price", {})
    latest = price.get("latest", 0)
    high_20d = price.get("high_20d", 0)
    low_20d = price.get("low_20d", 0)
    change_5d = price.get("change_pct_5d", 0)
    change_20d = price.get("change_pct_20d", 0)

    if latest >= high_20d * 0.95:
        trend_score += 3
        trend_detail.append("接近20日新高 +3")
    if change_20d and change_20d > 10:
        trend_score += 2
        trend_detail.append("20日涨幅>10% +2")
    if change_20d and change_20d < -10:
        trend_score -= 2
        trend_detail.append("20日跌幅>10% -2")
    if change_5d and change_5d > 5:
        trend_score += 1
        trend_detail.append("5日涨幅>5% +1")

    trend_score = max(0, min(15, trend_score))

    # ── 入场就绪度 (0 ~ 10) ──
    entry_score = 5
    entry_detail = []

    # KDJ 信号
    kdj = ta.get("kdj", {})
    if kdj.get("signal") == "低位金叉机会":
        entry_score += 2
        entry_detail.append("KDJ低位金叉 +2")
    elif kdj.get("signal") == "高位死叉风险":
        entry_score -= 2
        entry_detail.append("KDJ高位死叉 -2")

    # K线形态 — 反转形态序列加权
    candles = ta.get("candlestick", [])
    recent_bullish = [c for c in candles[-5:] if c.get("direction") == "bullish"]
    recent_bearish = [c for c in candles[-5:] if c.get("direction") == "bearish"]
    if len(recent_bullish) >= 3:
        entry_score += 2
        entry_detail.append(f"近5日{len(recent_bullish)}个看涨形态 +2(底部反转信号)")
    elif len(recent_bullish) >= 2:
        entry_score += 1
        entry_detail.append(f"近5日{len(recent_bullish)}个看涨形态 +1")
    if len(recent_bearish) >= 3:
        entry_score -= 2
        entry_detail.append(f"近5日{len(recent_bearish)}个看跌形态 -2(顶部反转信号)")
    elif len(recent_bearish) >= 2:
        entry_score -= 1
        entry_detail.append(f"近5日{len(recent_bearish)}个看跌形态 -1")

    # 布林带宽
    if boll.get("bandwidth") == "极度收窄":
        entry_score += 1
        entry_detail.append("布林极度收窄(变盘前兆) +1")

    entry_score = max(0, min(10, entry_score))

    return {
        "technical_timing": timing,
        "trend_breakout": trend_score,
        "entry_readiness": entry_score,
        "timing_detail": timing_detail,
        "trend_detail": trend_detail,
        "entry_detail": entry_detail,
    }


def score_fundamental(data: dict) -> dict:
    """基本面评分 (0~25)。四维：PE位置 + 盈利增速 + 利润率质量 + 机构覆盖。"""
    fundamental_score = 10  # 基准中性
    detail = []

    # key 别名：stock_valuation.json 用 industry_valuation_comparison / scale_comparison
    valuation = data.get("valuation") or data.get("industry_valuation_comparison", {})
    forecast = data.get("forecast_eps") or data.get("profit_forecast_eps", {})
    scale = data.get("scale") or data.get("scale_comparison", {})

    # ── 维度1：PE 位置（相对行业中值）──
    val_data = valuation.get("data", [valuation] if not isinstance(valuation, dict) else [])
    if isinstance(valuation, dict) and "data" in valuation:
        val_data = valuation["data"]
        if isinstance(val_data, dict):
            val_data = [val_data]

    pe = pe_median = None
    if val_data and isinstance(val_data, list) and len(val_data) > 0:
        v = val_data[0] if isinstance(val_data[0], dict) else {}
        pe = v.get("PE_TTM", v.get("pe_ttm", None))
        pe_median = v.get("PE_Median", v.get("pe_median", None))

        if pe is not None and pe_median is not None and pe_median > 0:
            try:
                pe, pe_median = float(pe), float(pe_median)
                if pe < pe_median * 0.7:
                    fundamental_score += 3
                    detail.append(f"PE({pe}) < 行业中值({pe_median})×0.7 +3")
                elif pe > pe_median * 1.5:
                    fundamental_score -= 2
                    detail.append(f"PE({pe}) > 行业中值({pe_median})×1.5 -2")
            except (ValueError, TypeError):
                pass

    # ── 维度2：盈利增速（从一致预期推算）──
    forecast_data = forecast.get("data", [])
    if forecast_data and len(forecast_data) > 0:
        # 取最新年份的 EPS 预测
        eps_forecasts = []
        for item in forecast_data:
            eps = item.get("每股收益", item.get("EPS", item.get("eps", None)))
            year = item.get("预测年度", item.get("year", item.get("forecast_year", "")))
            if eps is not None:
                try:
                    eps_forecasts.append((str(year), float(eps)))
                except (ValueError, TypeError):
                    pass

        # 尝试计算增速：最近两个预测年度
        eps_forecasts.sort(key=lambda x: x[0])
        if len(eps_forecasts) >= 2:
            eps_cur = eps_forecasts[-2][1]  # 当前年
            eps_next = eps_forecasts[-1][1]  # 下一年
            if eps_cur > 0:
                growth = (eps_next / eps_cur - 1) * 100
                if growth > 30:
                    fundamental_score += 3
                    detail.append(f"盈利增速 {growth:.0f}%(>30%) +3")
                elif growth > 10:
                    fundamental_score += 1
                    detail.append(f"盈利增速 {growth:.0f}%(10-30%) +1")
                elif growth < -10:
                    fundamental_score -= 2
                    detail.append(f"盈利增速 {growth:.0f}%(<-10%) -2")
                elif growth < 0:
                    fundamental_score -= 1
                    detail.append(f"盈利增速 {growth:.0f}%(负增长) -1")
    else:
        detail.append("无一致预期数据，盈利增速无法评估")

    # ── 维度3：利润率质量（从同业规模对比）──
    # scale 数据含同业的净利率/毛利率，摘目标 vs 行业中值
    scale_list = scale.get("data", scale if isinstance(scale, list) else [])
    if isinstance(scale, dict) and "data" in scale:
        scale_list = scale.get("data", scale_list)
    if not isinstance(scale_list, list):
        scale_list = []

    if scale_list and len(scale_list) > 1:
        net_margins = []
        target_nm = None
        for item in scale_list:
            nm = item.get("净利率", item.get("net_margin", None))
            is_target = item.get("is_target", False)
            if nm is not None:
                try:
                    nm_val = float(nm)
                    net_margins.append(nm_val)
                    if is_target:
                        target_nm = nm_val
                except (ValueError, TypeError):
                    pass

        if target_nm is not None and len(net_margins) >= 3:
            net_margins.sort()
            median = net_margins[len(net_margins) // 2]
            if median > 0:
                ratio = target_nm / median
                if ratio > 1.5:
                    fundamental_score += 3
                    detail.append(f"净利率({target_nm:.1f}%)远超行业中值({median:.1f}%) +3")
                elif ratio > 1.0:
                    fundamental_score += 1
                    detail.append(f"净利率({target_nm:.1f}%)高于行业中值({median:.1f}%) +1")
                elif ratio < 0.5:
                    fundamental_score -= 1
                    detail.append(f"净利率({target_nm:.1f}%)远低于行业中值({median:.1f}%) -1")
    else:
        detail.append("无同业规模数据，利润率无法评估")

    # ── 维度4：机构覆盖 ──
    if forecast_data and len(forecast_data) > 0:
        fundamental_score += 2
        detail.append(f"有机构覆盖({len(forecast_data)}家) +2")
    else:
        detail.append("无机构覆盖 中性")

    # ── 财务数据缺失标注 ──
    if not data.get("financial"):
        detail.append("⚠️ 财务三表/杜邦分析缺失，部分维度（ROE趋势/现金流质量）无法评估")

    fundamental_score = max(0, min(25, fundamental_score))

    return {
        "fundamental_quality": fundamental_score,
        "fundamental_detail": detail,
    }


def score_full(data: dict) -> dict:
    """全维度综合评分 (0~100)。"""
    tech = score_technical(data)
    fund = score_fundamental(data)

    auto_score = (
        max(0, (tech["technical_timing"] + 10) / 20 * 40)  # 择时分映射 0-40
        + max(0, tech["trend_breakout"] / 15 * 20)          # 趋势突破映射 0-20
        + max(0, tech["entry_readiness"] / 10 * 15)         # 入场就绪映射 0-15
        + max(0, fund["fundamental_quality"] / 25 * 25)     # 基本面映射 0-25 (当前受限)
    )

    risk_flags = []
    # 风控标记
    if tech["technical_timing"] <= -5:
        risk_flags.append("择时分严重偏空")
    if data.get("ta", {}).get("macd", {}).get("divergence") == "顶背离":
        risk_flags.append("MACD顶背离")
    if data.get("ta", {}).get("rsi", {}).get("zone") == "严重超买":
        risk_flags.append("RSI严重超买")
    if not risk_flags:
        risk_flags.append("无明显风控信号")

    return {
        "technical_timing": tech["technical_timing"],
        "trend_breakout": tech["trend_breakout"],
        "entry_readiness": tech["entry_readiness"],
        "fundamental_quality": fund["fundamental_quality"],
        "auto_score": round(auto_score, 1),
        "risk_flags": risk_flags,
        "timing_detail": tech["timing_detail"],
        "trend_detail": tech["trend_detail"],
        "entry_detail": tech["entry_detail"],
        "fundamental_detail": fund["fundamental_detail"],
    }


def compute_scores(mode: str, data: dict) -> dict:
    """根据模式计算评分。"""
    if mode == "technical":
        return score_technical(data)
    elif mode == "fundamental":
        return score_fundamental(data)
    elif mode == "full":
        return score_full(data)
    else:
        return {"error": f"未知模式: {mode}，可选: technical/fundamental/full"}


def main():
    parser = argparse.ArgumentParser(description="多维度评分引擎")
    parser.add_argument("--mode", type=str, default="full", help="technical/fundamental/full")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    args = parser.parse_args()

    data = json.loads(args.input) if args.input else json.load(sys.stdin)

    # ── 统一解包：处理中间层标准封装 {success, data, meta} ──
    if isinstance(data, dict) and "data" in data:
        inner = data["data"]
        if isinstance(inner, dict) and len(inner) > 0:
            data = inner

    # ── technical 模式：裸 K 线数组 → 包装为 ta 结构 ──
    if args.mode == "technical" and isinstance(data, list):
        data = {"ta": {}, "_raw_kline": data}

    result = compute_scores(args.mode, data)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
