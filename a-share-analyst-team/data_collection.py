#!/usr/bin/env python3
"""
data_collection.py — a-share-analyst Step 0 数据采集脚本

用途：主 Agent 在 execute_code 中执行，批量调用 a-share-market 中间层函数，
      组装标准 data_package JSON。

用法：
  python data_collection.py --symbol 600519 [--user-input "..."]
  或从环境变量: SYMBOL=600519 USER_INPUT="..." python data_collection.py

并发规则：
  - 同源 ≤2 并发（新浪/腾讯/同花顺/PAE/EM 等各自不超2）
  - Baostock 源禁止并发，必须串行
  - 批次间 random.uniform(1, 2) sleep

版本：v0.1 (2026-06-15)
状态：✅ 行情数据就绪 | ❌ 财务中间层待就绪 | ❌ 宏观数据待就绪
"""

import os
import json
import sys
import time
import random
import argparse
from typing import Any, Optional

# ── 禁止 baostock 污染 stdout ──
_original_stdout_fd = os.dup(1)
_devnull_fd = os.open(os.devnull, os.O_WRONLY)
os.dup2(_devnull_fd, 1)  # 导入期间静默 baostock 的 login/logout 消息

SYMBOL: str = ""
USER_INPUT: str = ""


# ═══════════════════════════════════════════════════════════════
# 中间层函数包装 — 统一调用接口 + 异常处理
# ═══════════════════════════════════════════════════════════════

def _safe_call(func, *args, **kwargs) -> dict:
    """包装中间层函数调用，统一异常处理，返回标准 dict。"""
    name = kwargs.pop("_name", func.__name__)
    try:
        result = func(*args, **kwargs)
        if isinstance(result, dict):
            if not result.get("success", True):
                return {"success": False, "error": result.get("error", "unknown"), "source": result.get("source", "?"), "_func": name}
            return {**result, "_func": name}
        return {"success": True, "data": result, "_func": name}
    except Exception as e:
        return {"success": False, "error": str(e), "_func": name}


# ═══════════════════════════════════════════════════════════════
# 数据采集主流程
# ═══════════════════════════════════════════════════════════════

def collect_all(symbol: str, user_input: str = "") -> dict:
    """
    按源分组批量采集全部数据，组装 data_package。

    返回格式：
    {
        "symbol": "600519",
        "user_input": "...",
        "market": {...},
        "stock": {...},
        "financial": {...},   # 当前全空
        "macro": {...},       # 当前全空
        "meta": {"collected_at": "ISO8601", "gaps": [...]}
    }
    """
    gaps: list[str] = []

    # ── 导入中间层函数 ──
    try:
        # 市场级
        from a_share_market_middleware.overall.index_quotes import get_index_quotes
        from a_share_market_middleware.overall.market import (
            get_market_breadth, get_market_activity,
            get_northbound_flow, get_margin_summary,
        )
        from a_share_market_middleware.overall.index_ import get_index_kline
        from a_share_market_middleware.sector.board import get_board_spot, get_board_fund_flow
        from a_share_market_middleware.sector.concept import get_concept_spot

        # 个股级
        from a_share_market_middleware.stock.realtime import get_realtime_quote
        from a_share_market_middleware.stock.kline import get_daily_kline, get_minute_kline
        from a_share_market_middleware.stock.flow import get_individual_fund_flow
        from a_share_market_middleware.stock.comparison import (
            get_industry_valuation_comparison, get_scale_comparison,
        )
        from a_share_market_middleware.stock.profile import get_company_profile
        from a_share_market_middleware.stock.research import (
            get_profit_forecast_eps, get_profit_forecast_metrics,
            get_research_reports,
        )
        from a_share_market_middleware.stock.lhb import get_lhb_stat
        from a_share_market_middleware.stock.dzjy import get_dzjy_stat
        from a_share_market_middleware.stock.holder import (
            get_shareholder_count, get_top10_shareholders,
            get_shareholder_changes, get_fund_holders,
        )
        from a_share_market_middleware.stock.margin import get_margin_detail
        from a_share_market_middleware.stock.gpzy import get_pledge_info
        from a_share_market_middleware.stock.penalty import get_regulatory_penalties

        # 财务中间层（如已安装）
        try:
            from a_share_finance_middleware.finance import get_financial_abstract, get_financial_indicators
            _FINANCE_READY = True
        except ImportError:
            _FINANCE_READY = False

    except ImportError as e:
        print(json.dumps({"success": False, "error": f"中间层导入失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    # ── 恢复 stdout ──
    os.dup2(_original_stdout_fd, 1)
    os.close(_devnull_fd)

    results: dict[str, Any] = {}

    # ═══════════════════════════════════════════════
    # Batch 1: 腾讯源 (tx, tx_http) — 2并发
    #   get_index_quotes (tx) + get_daily_kline (tx_http)
    # ═══════════════════════════════════════════════
    print("[Batch 1] 腾讯源: 指数行情 + 日K线", file=sys.stderr)
    # 串行调以避免同源并发（execute_code 中 async 不可用）
    results["index"] = _safe_call(get_index_quotes, _name="get_index_quotes")
    time.sleep(random.uniform(0.5, 1.0))
    results["kline_daily"] = _safe_call(get_daily_kline, symbol, _name="get_daily_kline")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 2: 新浪源 (sina, sina_http) — 2并发
    #   get_minute_kline(60) + get_minute_kline(30)
    #   传 start_date 确保足够数据量（中间层 lookback_days 自适应，显式传更安全）
    # ═══════════════════════════════════════════════
    print("[Batch 2] 新浪源: 分钟K线(60+30)", file=sys.stderr)
    from datetime import date, timedelta
    today = date.today()
    s60 = (today - timedelta(days=120)).strftime("%Y%m%d")  # 60min: 120日历日
    s30 = (today - timedelta(days=60)).strftime("%Y%m%d")   # 30min: 60日历日
    results["kline_60min"] = _safe_call(get_minute_kline, symbol, period="60",
                                        start_date=s60, _name="get_minute_kline(60)")
    time.sleep(random.uniform(0.5, 1.0))
    results["kline_30min"] = _safe_call(get_minute_kline, symbol, period="30",
                                        start_date=s30, _name="get_minute_kline(30)")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 3: 直调源 (legulegu, akshare HTML) — 2并发
    #   get_northbound_flow + get_market_activity
    # ═══════════════════════════════════════════════
    print("[Batch 3] 直调源: 北向 + 涨跌停", file=sys.stderr)
    results["northbound"] = _safe_call(get_northbound_flow, _name="get_northbound_flow")
    time.sleep(random.uniform(0.5, 1.0))
    results["activity"] = _safe_call(get_market_activity, _name="get_market_activity")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 4: 市场指标 (直调+legulegu) — 串行
    #   get_market_breadth + get_margin_summary
    # ═══════════════════════════════════════════════
    print("[Batch 4] 市场指标: 宽度 + 两融", file=sys.stderr)
    results["breadth"] = _safe_call(get_market_breadth, _name="get_market_breadth")
    time.sleep(random.uniform(0.5, 1.0))
    results["margin"] = _safe_call(get_margin_summary, _name="get_margin_summary")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 5: PAE 源 — 2并发
    #   get_board_spot("industry") + get_concept_spot()
    # ═══════════════════════════════════════════════
    print("[Batch 5] PAE: 行业+概念排名", file=sys.stderr)
    results["industry_spot"] = _safe_call(get_board_spot, "industry", _name="get_board_spot(industry)")
    time.sleep(random.uniform(0.5, 1.0))
    results["concept_spot"] = _safe_call(get_concept_spot, _name="get_concept_spot")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 6: PAE 资金流 — 2并发
    #   get_board_fund_flow("industry") + get_board_fund_flow("concept")
    # ═══════════════════════════════════════════════
    print("[Batch 6] PAE: 行业+概念资金流", file=sys.stderr)
    results["industry_flow"] = _safe_call(get_board_fund_flow, "industry", _name="get_board_fund_flow(industry)")
    time.sleep(random.uniform(0.5, 1.0))
    results["concept_flow"] = _safe_call(get_board_fund_flow, "concept", _name="get_board_fund_flow(concept)")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 7: 个股 — 腾讯源 (realtime)
    #   get_realtime_quote (tx)
    # ═══════════════════════════════════════════════
    print("[Batch 7] 个股行情: 实时 + 资金流", file=sys.stderr)
    results["quote"] = _safe_call(get_realtime_quote, symbol, _name="get_realtime_quote")
    time.sleep(random.uniform(0.5, 1.0))
    # PAE 主力资金 (不同源，可并发)
    results["fund_flow"] = _safe_call(get_individual_fund_flow, symbol, _name="get_individual_fund_flow")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 8: 个股 — EM 源 — 2并发
    #   get_valuation_comparison + get_scale_comparison
    # ═══════════════════════════════════════════════
    print("[Batch 8] EM: 估值对比 + 规模对比", file=sys.stderr)
    results["valuation"] = _safe_call(get_industry_valuation_comparison, symbol, _name="get_industry_valuation_comparison")
    time.sleep(random.uniform(0.5, 1.0))
    results["scale"] = _safe_call(get_scale_comparison, symbol, _name="get_scale_comparison")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 9: 个股 — EM 源（串行，避免同源并发）
    #   get_company_profile + get_profit_forecast_eps + get_profit_forecast_metrics
    # ═══════════════════════════════════════════════
    print("[Batch 9] EM: 概况 + 盈利预测", file=sys.stderr)
    results["profile"] = _safe_call(get_company_profile, symbol, _name="get_company_profile")
    time.sleep(random.uniform(0.5, 1.0))
    results["forecast_eps"] = _safe_call(get_profit_forecast_eps, symbol, _name="get_profit_forecast_eps")
    time.sleep(random.uniform(0.5, 1.0))
    results["forecast_metrics"] = _safe_call(get_profit_forecast_metrics, symbol, _name="get_profit_forecast_metrics")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 10: 个股 — 同花顺/混合源 — 串行
    #   股东 + 龙虎榜 + 大宗交易
    # ═══════════════════════════════════════════════
    print("[Batch 10] 股东 + 龙虎榜 + 大宗", file=sys.stderr)
    results["shareholder_count"] = _safe_call(get_shareholder_count, symbol, _name="get_shareholder_count")
    time.sleep(random.uniform(0.5, 1.0))
    results["top10"] = _safe_call(get_top10_shareholders, symbol, _name="get_top10_shareholders")
    time.sleep(random.uniform(0.5, 1.0))
    results["shareholder_changes"] = _safe_call(get_shareholder_changes, symbol, _name="get_shareholder_changes")
    time.sleep(random.uniform(0.5, 1.0))
    results["lhb"] = _safe_call(get_lhb_stat, symbol, _name="get_lhb_stat")
    time.sleep(random.uniform(0.5, 1.0))
    results["dzjy"] = _safe_call(get_dzjy_stat, symbol, _name="get_dzjy_stat")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 11: 个股 — 混合源 收尾
    #   研报 + 基金持仓 + 融资融券 + 质押
    # ═══════════════════════════════════════════════
    print("[Batch 11] 研报 + 基金 + 两融 + 质押", file=sys.stderr)
    results["research_reports"] = _safe_call(get_research_reports, symbol, _name="get_research_reports")
    time.sleep(random.uniform(0.5, 1.0))
    results["fund_holders"] = _safe_call(get_fund_holders, symbol, _name="get_fund_holders")
    time.sleep(random.uniform(0.5, 1.0))
    results["margin_detail"] = _safe_call(get_margin_detail, symbol, today.strftime("%Y-%m-%d"), _name="get_margin_detail")
    time.sleep(random.uniform(0.5, 1.0))
    results["pledge"] = _safe_call(get_pledge_info, symbol, _name="get_pledge_info")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 12: 指数K线 (沪深300) — 用于 Beta 计算
    # ═══════════════════════════════════════════════
    print("[Batch 12] 指数K线: 沪深300", file=sys.stderr)
    results["index_kline_000300"] = _safe_call(get_index_kline, "000300", _name="get_index_kline(000300)")
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 13: 监管处罚（新浪聚合，串行）
    #   get_regulatory_penalties
    # ═══════════════════════════════════════════════
    print("[Batch 13] 监管处罚 (新浪)", file=sys.stderr)
    # 从 profile 提取股票简称
    stock_name = None
    profile = results.get("profile", {})
    if profile.get("success") and profile.get("data"):
        stock_name = profile["data"][0].get("股票简称") or profile["data"][0].get("name")
    results["penalties"] = _safe_call(
        get_regulatory_penalties, symbol, stock_name=stock_name,
        _name="get_regulatory_penalties"
    )
    time.sleep(random.uniform(1, 2))

    # ═══════════════════════════════════════════════
    # Batch 14: 财务摘要（如中间层就绪）
    # ═══════════════════════════════════════════════
    if _FINANCE_READY:
        print("[Batch 14] 财务摘要 (finance middleware)", file=sys.stderr)
        results["financial_abstract"] = _safe_call(get_financial_abstract, symbol, _name="get_financial_abstract")
        time.sleep(random.uniform(0.5, 1.0))
        results["financial_indicators"] = _safe_call(get_financial_indicators, symbol, _name="get_financial_indicators")
        time.sleep(random.uniform(1, 2))

    # ──── 组装 data_package ────

    data_package = {
        "symbol": symbol,
        "user_input": user_input,
        "market": {
            "index": results.get("index", {}),
            "breadth": results.get("breadth", {}),
            "activity": results.get("activity", {}),
            "northbound": results.get("northbound", {}),
            "margin": results.get("margin", {}),
            "industry_spot": results.get("industry_spot", {}),
            "concept_spot": results.get("concept_spot", {}),
            "industry_flow": results.get("industry_flow", {}),
            "concept_flow": results.get("concept_flow", {}),
        },
        "stock": {
            "quote": results.get("quote", {}),
            "kline_daily": results.get("kline_daily", {}),
            "kline_60min": results.get("kline_60min", {}),
            "kline_30min": results.get("kline_30min", {}),
            # 周K线由 daily kline 聚合，此处不单独采集
            "fund_flow": results.get("fund_flow", {}),
            "valuation": results.get("valuation", {}),
            "scale": results.get("scale", {}),
            "profile": results.get("profile", {}),
            "forecast_eps": results.get("forecast_eps", {}),
            "forecast_metrics": results.get("forecast_metrics", {}),
            "lhb": results.get("lhb", {}),
            "dzjy": results.get("dzjy", {}),
            "shareholder_count": results.get("shareholder_count", {}),
            "top10_shareholders": results.get("top10", {}),
            "shareholder_changes": results.get("shareholder_changes", {}),
            "research_reports": results.get("research_reports", {}),
            "fund_holders": results.get("fund_holders", {}),
            "margin_detail": results.get("margin_detail", {}),
            "pledge": results.get("pledge", {}),
            "index_kline_000300": results.get("index_kline_000300", {}),
            "penalties": results.get("penalties", {}),
        },
        "financial": {
            "abstract": results.get("financial_abstract", {"success": False, "error": "财务中间层未安装", "_func": "get_financial_abstract"}),
            "indicators": results.get("financial_indicators", {"success": False, "error": "财务中间层未安装", "_func": "get_financial_indicators"}),
            "dupont": {"success": False, "error": "财务中间层未就绪", "_func": "get_dupont"},
            "growth": {"success": False, "error": "财务中间层未就绪", "_func": "get_growth_comparison"},
        },
        "macro": {
            # ❌ 第三中间层未建
            "indicators": {"success": False, "error": "宏观数据源 get_macro_indicators() 未建", "_func": "get_macro_indicators"},
        },
        "meta": {
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "version": "v0.2",
            "gaps": [
                "financial_dupont_growth: 杜邦/成长对比待集成",
                "macro: get_macro_indicators() 未建 (CPI/PMI/LPR/社融/利差/汇率)",
                "board_history: PAE API 无日期参数，板块轮动历史需 cron 积累",
                "weekly_kline: 需由日线聚合，不单独采集",
                "concept_constituents: PAE 仅200概念(资源品为主), THS/新浪待集成",
            ],
        },
    }

    return data_package


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

def main():
    global SYMBOL, USER_INPUT

    parser = argparse.ArgumentParser(description="a-share-analyst Step 0 数据采集")
    parser.add_argument("--symbol", type=str, help="股票代码 (6位数字)")
    parser.add_argument("--user-input", type=str, default="", help="用户外部输入 (可选)")
    args = parser.parse_args()

    SYMBOL = args.symbol or ""
    USER_INPUT = args.user_input or ""

    if not SYMBOL:
        print(json.dumps({"success": False, "error": "缺少 --symbol 参数"}, ensure_ascii=False))
        sys.exit(1)

    print(f"[data_collection] 开始采集 {SYMBOL} ...", file=sys.stderr)
    start = time.time()

    data_package = collect_all(SYMBOL, USER_INPUT)

    elapsed = time.time() - start
    print(f"[data_collection] 完成, 耗时 {elapsed:.1f}s", file=sys.stderr)

    # 输出 JSON 到 stdout（主 Agent 捕获）
    print(json.dumps(data_package, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
