#!/usr/bin/env python3
"""
market_thermometer.py — 市场情绪温度计 v0.1

独立前置模块。读取中间层 8 个市场温度函数，按阈值输出 🔴🟡🟢 定性信号。
供给 Agent A brief 引用，替代 Agent 自行猜测指标含义。

用法:
  python market_thermometer.py              # 输出 JSON
  python market_thermometer.py --file out   # 写入 /tmp/market_thermometer.json
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

import numpy as np

SKILL_DIR = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()
DATA_DIR = SKILL_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════
# 指标 1: 北向资金活跃度
# ═══════════════════════════════════════════════════════════

def northbound_signal():
    """
    数据: get_northbound_flow() → 日频序列，字段 northMoney (亿元)
    方法: 当前成交额 vs 近60日分布

    阈值: [待评定]
    """
    from a_share_market_middleware.overall.market import get_northbound_flow
    r = get_northbound_flow()
    if not r.get("success"):
        return _missing("北向活跃度")

    data = r.get("data", [])
    if len(data) < 60:
        return _insufficient("北向活跃度", len(data), 60)

    values = [d["northMoney"] for d in data if d.get("northMoney") is not None]
    current = values[0]  # 最新在前
    hist = values[1:61]  # 近60日

    pct = round(sum(1 for v in hist if v < current) / len(hist) * 100, 1)

    # 🔴🟡🟢: [待评定阈值]
    # 默认用百分位法: >80分位🟢, 20-80🟡, <20🔴
    if pct >= 80:
        signal, label = "🟢", "外资高度活跃"
    elif pct >= 20:
        signal, label = "🟡", "正常"
    else:
        signal, label = "🔴", "外资冷清"

    return {
        "indicator": "北向活跃度",
        "value": f"{current:.0f}亿",
        "percentile": pct,
        "data_date": r["meta"].get("latest_date") or data[0].get("date", "?"),
        "signal": signal,
        "label": label,
        "source": "get_northbound_flow",
    }


# ═══════════════════════════════════════════════════════════
# 指标 2: 两融杠杆
# ═══════════════════════════════════════════════════════════

def margin_signal():
    """
    数据: get_margin_summary("YYYY-MM-DD") → 最近交易日融资/融券余额
    方法: 融资余额绝对值 + 融资买入额占比

    阈值: [待评定]
    点金原版: >1.5%🔴（单日增幅）, 稳步增长🟢

    问题:
      1. get_margin_summary 仅返回1条（最新交易日），无法做环比
      2. 替代方案: 用融资买入额/融资余额 判断杠杆活跃度
      3. 或者用 data 序列做环比（需确认函数是否支持多日查询）
    """
    from a_share_market_middleware.overall.market import get_margin_summary
    r = get_margin_summary()
    if not r.get("success"):
        return _missing("两融杠杆")

    data = r.get("data", [])
    if not data:
        return _missing("两融杠杆")

    today = data[0]
    rz_balance = today.get("融资余额", 0)  # 亿元
    rq_balance = today.get("融券余额", 0)
    rz_buy     = today.get("融资买入额", 0)
    date       = r["meta"].get("latest_date") or today.get("日期", "?")

    # 融资买入占余额比 — 衡量当日杠杆活跃度
    buy_ratio = round(rz_buy / rz_balance * 100, 2) if rz_balance else 0

    # 🔴🟡🟢: [待评定阈值]
    # 用买入占比替代环比变化（因函数仅返回1条）
    if buy_ratio > 15:
        signal, label = "🔴", f"杠杆过热 (买入占比{buy_ratio}%)"
    elif buy_ratio > 8:
        signal, label = "🟢", f"杠杆活跃 (买入占比{buy_ratio}%)"
    elif buy_ratio > 3:
        signal, label = "🟡", f"杠杆正常 (买入占比{buy_ratio}%)"
    else:
        signal, label = "🟡", f"杠杆冷清 (买入占比{buy_ratio}%)"

    return {
        "indicator": "两融杠杆",
        "value": f"融资{rz_balance:.0f}亿",
        "data_date": date,
        "rz_buy_ratio": buy_ratio,
        "signal": signal,
        "label": label,
        "source": "get_margin_summary",
    }


# ═══════════════════════════════════════════════════════════
# 指标 3: 涨跌停情绪
# ═══════════════════════════════════════════════════════════

def market_activity_signal():
    """
    数据: get_market_activity() → 涨跌停家数快照
    方法: 涨停数/跌停数 vs 阈值

    阈值: [待评定]
    点金原版: 涨停>50🟢, 跌停>20🔴

    问题:
      1. 全市场注册制后涨跌停家数基准变了，50/20 是否需要调整？
      2. 北交所涨跌停±30%，主板±10%，阈值是否应该分板？
      3. 炸板率没有直接数据源，如何获取？
    """
    from a_share_market_middleware.overall.market import get_market_activity
    r = get_market_activity()
    if not r.get("success"):
        return _missing("涨跌停情绪")

    data = r.get("data", [])
    # data 格式: [{"item": "上涨", "value": 1961}, {"item": "涨停", "value": 103}, ...]
    item_map = {d["item"]: d["value"] for d in data} if isinstance(data, list) else {}
    up_limit   = item_map.get("涨停", 0)
    down_limit = item_map.get("跌停", 0)

    # 🔴🟡🟢: [待评定阈值]
    if down_limit > 20:
        signal, label = "🔴", f"恐慌 (跌停{down_limit}家)"
    elif up_limit > 50:
        signal, label = "🟢", f"亢奋 (涨停{up_limit}家)"
    else:
        signal, label = "🟡", f"中性 (涨停{up_limit}/跌停{down_limit})"

    return {
        "indicator": "涨跌停情绪",
        "value": f"涨停{up_limit}/跌停{down_limit}",
        "up_limit": up_limit,
        "down_limit": down_limit,
        "data_date": r["meta"].get("latest_date") or (r["meta"].get("stat_date", "?")[:10] if r["meta"].get("stat_date") else "?"),
        "signal": signal,
        "label": label,
        "source": "get_market_activity",
    }


# ═══════════════════════════════════════════════════════════
# 指标 4: 拥挤度
# ═══════════════════════════════════════════════════════════

def congestion_signal():
    """
    数据: get_market_congestion() → 0~1 连续值
    方法: 直接按值域分档

    阈值: [待评定]
    当前假设: <0.2极低, >0.8极高

    问题:
      1. 0.2/0.8 是否合理？是否需要按市场状态（牛/熊/震荡）动态调整？
      2. 拥挤度的底层算法是什么？是否受单一行业/风格影响？
    """
    from a_share_market_middleware.overall.market import get_market_congestion
    r = get_market_congestion()
    if not r.get("success"):
        return _missing("拥挤度")

    val = r["meta"].get("latest_congestion")
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return _missing("拥挤度")

    val = round(val, 3)

    # 🔴🟡🟢: [待评定阈值]
    if val > 0.8:
        signal, label = "🔴", f"过度拥挤 ({val})"
    elif val < 0.2:
        signal, label = "🟢", f"极度冷清 ({val})"
    else:
        signal, label = "🟡", f"正常 ({val})"

    staleness = r["meta"].get("staleness_note")
    return {
        "indicator": "拥挤度",
        "value": val,
        "data_date": r["meta"].get("latest_date", "?"),
        "signal": signal,
        "label": label,
        "source": "get_market_congestion",
        **({"staleness_note": staleness} if staleness else {}),
    }


# ═══════════════════════════════════════════════════════════
# 指标 5: 股债利差
# ═══════════════════════════════════════════════════════════

def ebs_signal():
    """
    数据: get_ebs() → latest_ebs + latest_ebs_ma
    方法: ebs vs ebs_ma

    阈值: [待评定]
    当前假设: ebs>ma 权益有吸引力, ebs<ma 权益无吸引力

    问题:
      1. 差值多少算"显著"？±0.2% 是随意拍的
      2. ebs_ma 的周期是多少？MA 参数是否可调？
    """
    from a_share_market_middleware.overall.market import get_ebs
    r = get_ebs()
    if not r.get("success"):
        return _missing("股债利差")

    ebs = r["meta"].get("latest_ebs")
    ebs_ma = r["meta"].get("latest_ebs_ma")
    if ebs is None or ebs_ma is None:
        return _missing("股债利差")

    # ebs 为小数（0.0546=5.46%），转百分比显示
    gap_pct = round((ebs - ebs_ma) * 100, 2)  # 百分点
    ebs_pct = round(ebs * 100, 2)
    ebs_ma_pct = round(ebs_ma * 100, 2)

    # 🔴🟡🟢: [待评定阈值]
    if gap_pct > 0.2:
        signal, label = "🟢", f"权益有吸引力 (gap=+{gap_pct}pp)"
    elif gap_pct < -0.2:
        signal, label = "🔴", f"权益无吸引力 (gap={gap_pct}pp)"
    else:
        signal, label = "🟡", f"中性 (gap={gap_pct}pp)"

    return {
        "indicator": "股债利差",
        "value": f"{ebs_pct}%",
        "ebs_ma": f"{ebs_ma_pct}%",
        "gap_pct": gap_pct,
        "data_date": r["meta"].get("latest_date", "?"),
        "signal": signal,
        "label": label,
        "source": "get_ebs",
    }


# ═══════════════════════════════════════════════════════════
# 指标 6: 巴菲特指数（总市值/GDP）
# ═══════════════════════════════════════════════════════════

def buffett_signal():
    """
    数据: get_buffett_index() → latest_buffett + pct_all/pct_10y 分位
    方法: 当前值 vs 历史分位

    阈值: [待评定]
    当前假设: >90分位🔴高估, 50-90🟡, <50🟢低估

    问题:
      1. 90分位是否太宽松？巴菲特本人认为>100%就是高估
      2. 用全历史分位还是近10年分位？两者含义不同
      3. 不同经济周期下 GDP 结构变化，指标本身是否有系统性偏差？
    """
    from a_share_market_middleware.overall.market import get_buffett_index
    r = get_buffett_index()
    if not r.get("success"):
        return _missing("巴菲特指数")

    val = r["meta"].get("latest_buffett")
    pct_10y_raw = r["meta"].get("pct_10y", {})
    pct_10y = pct_10y_raw.get("value", None) if isinstance(pct_10y_raw, dict) else pct_10y_raw
    if val is None:
        return _missing("巴菲特指数")

    # 🔴🟡🟢: [待评定阈值]
    if pct_10y is not None and pct_10y > 0.9:
        signal, label = "🔴", f"高估 (分位={pct_10y*100:.0f}%)"
    elif pct_10y is not None and pct_10y > 0.5:
        signal, label = "🟡", f"中等 (分位={pct_10y*100:.0f}%)"
    elif pct_10y is not None:
        signal, label = "🟢", f"低估 (分位={pct_10y*100:.0f}%)"
    else:
        signal, label = "🟡", f"{val}% (分位缺失)"

    return {
        "indicator": "巴菲特指数",
        "value": f"{val}%",
        "pct_10y": round(pct_10y * 100, 1) if pct_10y else None,
        "data_date": r["meta"].get("latest_date", "?"),
        "signal": signal,
        "label": label,
        "source": "get_buffett_index",
    }


# ═══════════════════════════════════════════════════════════
# 指标 7: 新高新低（市场宽度）
# ═══════════════════════════════════════════════════════════

def breadth_signal():
    """
    数据: get_market_breadth() → latest_high20 / latest_low20
    方法: 新高/新低比值

    阈值: [待评定]
    当前假设: >2🟢强势, 0.5~2🟡, <0.5🔴弱势

    问题:
      1. 比值还是绝对数？新高100/新低50 和 新高20/新低10 比值相同，含义不同
      2. 20日窗口是否合适？是否与均线周期一致？
      3. 极端市况下（千股跌停），比值失真怎么办？
    """
    from a_share_market_middleware.overall.market import get_market_breadth
    r = get_market_breadth()
    if not r.get("success"):
        return _missing("新高新低")

    high20 = r["meta"].get("latest_high20", 0)
    low20  = r["meta"].get("latest_low20", 0)
    ratio = round(high20 / low20, 2) if low20 > 0 else (999 if high20 > 0 else 1)

    # 🔴🟡🟢: [待评定阈值]
    if ratio > 2:
        signal, label = "🟢", f"强势 (新高{high20}/新低{low20})"
    elif ratio > 0.5:
        signal, label = "🟡", f"正常 (新高{high20}/新低{low20})"
    else:
        signal, label = "🔴", f"弱势 (新高{high20}/新低{low20})"

    return {
        "indicator": "新高新低",
        "value": f"新高{high20}/新低{low20}",
        "ratio": ratio,
        "data_date": r["meta"].get("latest_date", "?"),
        "signal": signal,
        "label": label,
        "source": "get_market_breadth",
    }


# ═══════════════════════════════════════════════════════════
# 指标 8: 指数估值分位
# ═══════════════════════════════════════════════════════════

def index_valuation_signal():
    """
    数据: get_index_pe("沪深300") → latest_weighted_pe + latest_weighted_pe_pct
    方法: PE 在历史中的分位

    阈值: [待评定]
    当前假设: >80分位🔴高估, 20-80🟡, <20🟢低估

    问题:
      1. 用沪深300代表全市场是否合适？是否应该加中证500/1000？
      2. PE分位 vs PB分位，哪个更适合做温度指标？
      3. 指数的成分股定期调整会导致PE跳变，如何平滑？
    """
    from a_share_market_middleware.overall.valuation import get_index_pe
    r = get_index_pe("沪深300")
    if not r.get("success"):
        return _missing("指数估值")

    pe = r["meta"].get("latest_weighted_pe")
    pct = r["meta"].get("latest_weighted_pe_pct")
    if pe is None or pct is None:
        return _missing("指数估值")

    pct_pct = round(pct * 100, 1)

    # 🔴🟡🟢: [待评定阈值]
    if pct > 0.8:
        signal, label = "🔴", f"高估 (PE={pe:.1f}, 分位={pct_pct}%)"
    elif pct > 0.2:
        signal, label = "🟡", f"中等 (PE={pe:.1f}, 分位={pct_pct}%)"
    else:
        signal, label = "🟢", f"低估 (PE={pe:.1f}, 分位={pct_pct}%)"

    return {
        "indicator": "指数估值",
        "value": f"PE={pe:.1f}",
        "percentile": pct_pct,
        "data_date": r["meta"].get("latest_date", "?"),
        "signal": signal,
        "label": label,
        "source": "get_index_pe(沪深300)",
    }


# ═══════════════════════════════════════════════════════════
# 指标 7: 龙虎榜（市场级）
# ═══════════════════════════════════════════════════════════

def lhb_market_signal():
    """
    数据: get_lhb_detail(date, date) → 当天全部上榜记录
    方法: 汇总全市场机构净买卖 + 上榜多空比

    阈值: [待评定]
    点金原版: 机构净卖出>2亿🔴 / 低位净买入🟢 / 炸板率飙升🟡

    问题:
      1. 点金用「机构净买卖额」，但我们只有「龙虎榜净买额」（含游资）
      2. 可以从「解读」字段提取机构专用数据
      3. 炸板率目前无法获取（需要封板后开板数据）
    """
    from a_share_market_middleware.ext.lhb import get_lhb_detail
    from datetime import date, timedelta

    # 向前找最近交易日（处理周末/节假日）
    d = date.today()
    data = []
    trade_date = "?"
    for _ in range(5):
        ds = d.strftime("%Y%m%d")
        r = get_lhb_detail(ds, ds)
        if r.get("success") and r.get("data"):
            data = r["data"]
            trade_date = r["meta"].get("latest_date", d.strftime("%Y-%m-%d"))
            break
        d -= timedelta(days=1)

    if not data:
        return {"indicator": "龙虎榜(市场)", "signal": "⚪", "label": "近5日无上榜记录", "source": "get_lhb_detail"}

    total_net = sum(d.get("龙虎榜净买额", 0) or 0 for d in data)
    net_buy_count = sum(1 for d in data if (d.get("龙虎榜净买额") or 0) > 0)
    net_sell_count = len(data) - net_buy_count

    # 从「解读」中提取机构信息
    inst_buy = 0
    inst_sell = 0
    for d in data:
        jd = d.get("解读", "")
        if "机构买入" in str(jd):
            inst_buy += 1
        if "机构卖出" in str(jd):
            inst_sell += 1

    buy_ratio = round(net_buy_count / len(data) * 100, 1) if data else 0

    # 🔴🟡🟢: [待评定阈值]
    if total_net > 5e8:
        signal, label = "🟢", f"净买入{total_net/1e8:.1f}亿 (多空{buy_ratio}%)"
    elif total_net < -5e8:
        signal, label = "🔴", f"净卖出{abs(total_net)/1e8:.1f}亿 (多空{buy_ratio}%)"
    elif buy_ratio > 55:
        signal, label = "🟢", f"偏多 (多空{buy_ratio}%)"
    elif buy_ratio < 45:
        signal, label = "🔴", f"偏空 (多空{buy_ratio}%)"
    else:
        signal, label = "🟡", f"均衡 (多空{buy_ratio}%)"

    return {
        "indicator": "龙虎榜(市场)",
        "value": f"上榜{len(data)}只",
        "total_net": round(total_net / 1e8, 2),  # 亿元
        "net_buy_count": net_buy_count,
        "net_sell_count": net_sell_count,
        "inst_buy": inst_buy,
        "inst_sell": inst_sell,
        "data_date": trade_date,
        "signal": signal,
        "label": label,
        "source": "get_lhb_detail",
    }


# ═══════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════

SIGNAL_FUNCTIONS = [
    northbound_signal,
    margin_signal,
    market_activity_signal,
    congestion_signal,
    ebs_signal,
    breadth_signal,
    lhb_market_signal,
]

def _missing(name: str) -> dict:
    return {"indicator": name, "value": "-", "signal": "⚪", "label": "数据缺失", "source": "-"}

def _insufficient(name: str, got: int, need: int) -> dict:
    return {"indicator": name, "value": "-", "signal": "⚪", "label": f"数据不足(仅{got}条,需{need})", "source": "-"}

def run_all() -> dict:
    """运行全部 8 个指标，输出结构化结果。"""
    indicators = []
    for fn in SIGNAL_FUNCTIONS:
        try:
            result = fn()
        except Exception as e:
            result = {"indicator": fn.__name__, "signal": "⚪", "label": f"计算异常: {e}", "source": "-"}
        indicators.append(result)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "indicators": indicators,
    }


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="市场情绪温度计 v0.1")
    parser.add_argument("--file", type=str, help="输出到文件（默认 stdout）")
    parser.add_argument("--indicator", type=str, help="单独跑某个指标")
    args = parser.parse_args()

    if args.indicator:
        fn_map = {fn.__name__: fn for fn in SIGNAL_FUNCTIONS}
        fn = fn_map.get(args.indicator)
        if fn:
            print(json.dumps(fn(), ensure_ascii=False, indent=2))
        else:
            print(f"未知指标: {args.indicator}")
            sys.exit(1)
    else:
        result = run_all()
        out = json.dumps(result, ensure_ascii=False, indent=2)

        if args.file:
            path = Path(args.file)
            if not path.is_absolute():
                path = DATA_DIR / path
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"✅ 写入 {path}")
        else:
            print(out)


if __name__ == "__main__":
    main()
