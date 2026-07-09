#!/usr/bin/env python3
"""
theme_detector.py — 主线识别辅助

输入：data_package.market (指数/宽度/行业/概念排名)
输出：市场环境 + 主线 + 伪主线 + 情绪周期

用法：
  python theme_detector.py --input '<json>'
"""

import json
import sys
import argparse


def _safe_list(data, key="data", default=None):
    """从中间层返回结构中提取列表。"""
    if default is None:
        default = []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get(key, data.get("data", default))
    return default


def analyze_market_structure(market_data: dict) -> dict:
    """分析市场结构：环境、主线、情绪。"""
    # 解包 collect_market.py 的标准封装 {success, data, meta}
    if "data" in market_data and isinstance(market_data.get("data"), dict):
        market_data = market_data["data"]
    result = {}

    # ── 1. 市场环境 ──
    env_evidence = []

    # 指数快照 (key: index_quotes)
    index_data = market_data.get("index_quotes", market_data.get("index", {}))
    if isinstance(index_data, dict) and index_data.get("data"):
        idx_dict = index_data["data"]
        if isinstance(idx_dict, dict):
            up_count = sum(1 for v in idx_dict.values() if isinstance(v, dict) and float(v.get("涨跌幅", 0)) > 0)
            down_count = sum(1 for v in idx_dict.values() if isinstance(v, dict) and float(v.get("涨跌幅", 0)) < 0)
            env_evidence.append(f"10大指数: {up_count}涨{down_count}跌")

    # 市场宽度 — key: market_breadth
    breadth = market_data.get("market_breadth", market_data.get("breadth", {}))
    if isinstance(breadth, dict):
        meta = breadth.get("meta", {})
        high20 = meta.get("latest_high20")
        low20 = meta.get("latest_low20")
        if high20 is not None or low20 is not None:
            env_evidence.append(f"20日新高{high20}/新低{low20}")

    # 涨跌停 — key: market_activity, kv-pair 结构 [{item, value}]
    activity = market_data.get("market_activity", market_data.get("activity", {}))
    act_data = _safe_list(activity)
    if act_data and isinstance(act_data[0], dict) and "item" in act_data[0]:
        # kv 对结构 → 转为扁平 dict
        act_flat = {r["item"]: r.get("value", 0) for r in act_data if isinstance(r, dict)}
        up_limit = int(act_flat.get("涨停", 0))
        down_limit = int(act_flat.get("跌停", 0))
    else:
        up_limit = down_limit = 0
    if up_limit or down_limit:
        env_evidence.append(f"涨停{up_limit}/跌停{down_limit}")

    # 环境判断
    if len(env_evidence) >= 2 and "涨" in env_evidence[0] and "跌" in env_evidence[0]:
        stage = "震荡"  # 默认
    else:
        stage = "数据不足"

    result["environment"] = {
        "stage": stage,
        "evidence": env_evidence,
    }

    # ── 2. 主线识别 ──
    main_themes = []
    industry_spot = _safe_list(market_data.get("board_spot_industry", market_data.get("industry_spot", {})))
    if industry_spot:
        for item in industry_spot[:5]:
            if isinstance(item, dict):
                name = item.get("板块名称", item.get("name", item.get("board_name", "?")))
                pct = float(item.get("涨跌幅", item.get("change_pct", item.get("pct_change", 0))))
                main_themes.append({
                    "name": name,
                    "change_pct": round(pct, 2),
                    "type": "industry",
                })

    concept_spot = _safe_list(market_data.get("concept_spot", {}))
    if concept_spot:
        for item in concept_spot[:5]:
            if isinstance(item, dict):
                name = item.get("板块名称", item.get("name", item.get("board_name", "?")))
                pct = float(item.get("涨跌幅", item.get("change_pct", item.get("pct_change", 0))))
                main_themes.append({
                    "name": name,
                    "change_pct": round(pct, 2),
                    "type": "concept",
                })

    # 排序取 Top 5
    main_themes.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    result["main_themes"] = main_themes[:5]

    # ── 3. 情绪周期 ──
    sentiment_stage = "无法判断"
    sentiment_evidence = []

    # kv 对结构 → 转为扁平 dict
    up_limit_count = 0
    act_data2 = _safe_list(market_data.get("market_activity", market_data.get("activity", {})))
    if act_data2 and isinstance(act_data2[0], dict) and "item" in act_data2[0]:
        act_flat2 = {r["item"]: r.get("value", 0) for r in act_data2 if isinstance(r, dict)}
        up_limit_count = int(act_flat2.get("涨停", 0))
        down_limit_count = int(act_flat2.get("跌停", 0))
        if up_limit_count > 100 and down_limit_count < 10:
            sentiment_stage = "活跃"
            sentiment_evidence.append(f"涨停{up_limit_count} >> 跌停{down_limit_count}")
        elif down_limit_count > 50:
            sentiment_stage = "恐慌"
            sentiment_evidence.append(f"跌停{down_limit_count}家")
        elif up_limit_count < 30:
            sentiment_stage = "低迷"
            sentiment_evidence.append(f"涨停仅{up_limit_count}家")

    result["sentiment_cycle"] = {
        "stage": sentiment_stage,
        "evidence": sentiment_evidence,
    }

    # ── 4. 北向 + 两融 ──
    northbound = market_data.get("northbound_flow", market_data.get("northbound", {}))
    nb_data = _safe_list(northbound)
    if nb_data:
        latest = nb_data[0] if len(nb_data) > 0 else {}
        result["northbound"] = {
            "latest": latest.get("northMoney", None),
            "label": "北向成交额",
            "unit": "亿元",
            "note": "成交量非净流向，不表示资金进出方向"
        }

    margin = market_data.get("margin_summary", market_data.get("margin", {}))
    mg_data = _safe_list(margin)
    if mg_data:
        latest = mg_data[0] if len(mg_data) > 0 else {}
        result["margin"] = {
            "balance": round(latest.get("margin_balance", latest.get("融资余额", 0)), 2),
            "label": "融资余额",
            "unit": "亿元",
        }

    return result


def main():
    parser = argparse.ArgumentParser(description="主线识别")
    parser.add_argument("--input", type=str, help="JSON 字符串")
    args = parser.parse_args()

    data = json.loads(args.input) if args.input else json.load(sys.stdin)
    result = analyze_market_structure(data)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
