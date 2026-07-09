#!/usr/bin/env python3
"""
st_risk.py — A 股 ST/*ST 风险预测量化脚本

从 data_package 读取财务/行情数据，计算 R1-R4 量化红线 + E1-E3 事实证据，
输出双轴结果（风险等级 + 预测可信度）。

vibe-trading ashare-pre-st-filter 的量化逻辑移植，适配 a-share-analyst 数据源。
输入：JSON via stdin 或 --input file（数据由主 Agent Step 0 采集）
输出：JSON 到 stdout

R1: 营收+净利润红线（扣非前后孰低）
R2: 年末净资产红线
R3: 分红达标前瞻
R4: 连续亏损/扣非亏损链
E1: 审计意见（事实）
E2: 监管处罚（事实，需 st_penalties.py 输出）
E3: 交易类临界预警（1元退市/市值退市）
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── 板块阈值表 ──────────────────────────────────────
# 主板 / 创业板 / 科创板 三套标准
THRESHOLDS = {
    "主板": {
        "revenue": 300_000_000,       # 营收红线 3亿
        "mv_delist": 500_000_000,     # 市值退市线 5亿
        "div_cumulative": 50_000_000, # 三年累计分红 5000万
        "div_pct_net": 0.30,          # < 年均净利润 30%
    },
    "创业板": {
        "revenue": 100_000_000,       # 1亿
        "mv_delist": 300_000_000,     # 3亿
        "div_cumulative": 30_000_000, # 3000万
        "div_pct_net": 0.30,
    },
    "科创板": {
        "revenue": 100_000_000,       # 1亿
        "mv_delist": 300_000_000,     # 3亿
        "div_cumulative": 30_000_000, # 3000万
        "div_pct_net": 0.30,
    },
}

# ── 板块识别 ──────────────────────────────────────
def _classify_board(ts_code: str) -> str:
    """根据代码前缀识别板块"""
    code = ts_code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if code.startswith("688"):
        return "科创板"
    if code.startswith("30"):
        return "创业板"
    return "主板"


# ── R1: 营收 + 净利润红线 ──────────────────────────
def _r1_revenue_profit(fin: dict, board: str, t: dict) -> dict:
    """
    预测全年营收和净利润，按 min(归母净利润, 扣非净利润) 判定。
    fin: financial_abstract 输出
    t: 板块阈值
    """
    result = {"risk": "low", "confidence": "low", "details": {}}

    # 尝试从财务摘要中提取最新数据
    data = fin.get("data", [])
    if not data:
        result["risk"] = "data_insufficient"
        result["details"]["reason"] = "无财务摘要数据"
        return result

    # 取最新一期
    latest = data[0] if data else {}

    # 净利润（归母）
    net_profit = _parse_num(latest.get("净利润")) or _parse_num(latest.get("归属于母公司所有者的净利润"))
    # 营收
    revenue = _parse_num(latest.get("营业收入")) or _parse_num(latest.get("营业总收入"))

    # 扣非净利润 — 财务摘要通常不含，标记为缺失
    profit_dedt = _parse_num(latest.get("扣除非经常性损益后的净利润")) or _parse_num(latest.get("扣非净利润"))

    result["details"]["net_profit"] = net_profit
    result["details"]["revenue"] = revenue
    result["details"]["profit_dedt"] = profit_dedt
    result["details"]["stat_date"] = latest.get("统计日期") or latest.get("报告日") or "未知"

    if net_profit is None and revenue is None:
        result["risk"] = "data_insufficient"
        result["details"]["reason"] = "净利润和营收均为空"
        return result

    # 扣非前后孰低
    if profit_dedt is not None and net_profit is not None:
        worst_profit = min(net_profit, profit_dedt)
        result["details"]["worst_profit"] = worst_profit
        result["details"]["has_deducted"] = True
        result["confidence"] = "medium"
    elif net_profit is not None:
        worst_profit = net_profit
        result["details"]["worst_profit"] = worst_profit
        result["details"]["has_deducted"] = False
        result["details"]["warning"] = "扣非净利润缺失，仅用归母净利润判定，可能漏掉造壳公司"
    else:
        result["risk"] = "data_insufficient"
        return result

    # 判定
    revenue_threshold = t["revenue"]

    if worst_profit < 0 and revenue is not None and revenue < revenue_threshold:
        result["risk"] = "high"
        result["details"]["trigger"] = f"净利润为负({worst_profit}) 且 营收({revenue}) < {revenue_threshold}"
    elif worst_profit < 0 and revenue is not None and revenue >= revenue_threshold:
        result["risk"] = "medium"
        result["details"]["trigger"] = f"净利润为负({worst_profit}) 但 营收({revenue}) >= {revenue_threshold}"
    elif revenue is not None and revenue < revenue_threshold * 1.2:
        result["risk"] = "medium"
        result["details"]["trigger"] = f"营收({revenue}) 逼近阈值({revenue_threshold})，buffer=1.2x"
    else:
        result["details"]["trigger"] = "营收和净利润均在安全区间"

    return result


# ── R2: 年末净资产红线 ─────────────────────────────
def _r2_equity(fin: dict, board: str, t: dict, r1: dict) -> dict:
    """判断年末归母股东权益是否可能转负"""
    result = {"risk": "low", "confidence": "low", "details": {}}

    data = fin.get("data", [])
    if not data:
        result["risk"] = "data_insufficient"
        return result

    latest = data[0] if data else {}
    equity = (
        _parse_num(latest.get("归属于母公司股东权益合计"))
        or _parse_num(latest.get("所有者权益(或股东权益)合计"))
        or _parse_num(latest.get("股东权益合计"))
    )

    result["details"]["current_equity"] = equity

    if equity is None:
        result["risk"] = "data_insufficient"
        result["details"]["reason"] = "净资产数据缺失"
        return result

    if equity < 0:
        result["risk"] = "high"
        result["details"]["trigger"] = f"净资产已为负({equity})"
    elif equity < 100_000_000:
        result["risk"] = "medium"
        result["details"]["trigger"] = f"净资产({equity}) < 1亿元"
    else:
        result["details"]["trigger"] = "净资产充足"

    result["confidence"] = "medium"
    return result


# ── R4: 连续亏损链 ─────────────────────────────────
def _r4_consecutive_loss(fin: dict, board: str, t: dict, r1: dict) -> dict:
    """判断连续两年扣非前后净利润孰低者为负"""
    result = {"risk": "low", "confidence": "low", "details": {}}

    data = fin.get("data", [])
    if len(data) < 2:
        result["risk"] = "data_insufficient"
        result["details"]["reason"] = "财务摘要记录不足2期，无法判定连续亏损"
        return result

    current = data[0]
    previous = data[1] if len(data) > 1 else None

    cur_profit = _parse_num(current.get("净利润"))
    prev_profit = _parse_num(previous.get("净利润")) if previous else None

    result["details"]["current_profit"] = cur_profit
    result["details"]["previous_profit"] = prev_profit
    result["details"]["current_period"] = current.get("统计日期") or current.get("报告日")
    result["details"]["previous_period"] = previous.get("统计日期") or previous.get("报告日") if previous else None

    if cur_profit is None or prev_profit is None:
        result["risk"] = "data_insufficient"
        return result

    both_neg = cur_profit < 0 and prev_profit < 0

    if both_neg:
        # 还需叠加营收条件
        revenue = _parse_num(current.get("营业收入")) or _parse_num(current.get("营业总收入"))
        if revenue is not None and revenue < t["revenue"] * 1.5:
            result["risk"] = "high"
            result["details"]["trigger"] = f"连续两年亏损 + 营收({revenue}) < 阈值×1.5({t['revenue']*1.5})"
        else:
            result["risk"] = "medium"
            result["details"]["trigger"] = "连续两年亏损但营收远超阈值"
    elif cur_profit < 0:
        result["risk"] = "medium"
        result["details"]["trigger"] = "当前年预测亏损，去年盈利，未形成连续"
    elif prev_profit < 0 and cur_profit is not None and cur_profit < 0.5 * t["revenue"]:
        result["risk"] = "medium"
        result["details"]["trigger"] = "去年亏损，当前年盈利但接近零"

    result["confidence"] = "medium"
    return result


# ── E3: 交易类临界 ──────────────────────────────────
def _e3_trading_alert(price_data: dict, board: str, t: dict) -> dict:
    """1元退市预警 + 市值退市预警"""
    result = {"risk": "low", "details": {}}

    # 1 元退市检查
    klines = price_data.get("data", [])
    if klines:
        close_1_count = sum(1 for k in klines[:20] if _parse_num(k.get("收盘")) is not None and _parse_num(k.get("收盘")) < 1.0)
        result["details"]["days_below_1y"] = close_1_count
        if close_1_count >= 10:
            result["risk"] = "high"
            result["details"]["trigger_1y"] = f"近20日 {close_1_count} 天收盘价 < 1元"
        elif close_1_count >= 1:
            result["risk"] = "medium"
            result["details"]["trigger_1y"] = f"近20日 {close_1_count} 天收盘价 < 1元"

    # 市值退市检查
    rt = price_data.get("meta", {}).get("latest_total_mv")
    if rt is not None:
        result["details"]["total_mv"] = rt
        if rt < t["mv_delist"]:
            if result["risk"] != "high":
                result["risk"] = "high"
            result["details"]["trigger_mv"] = f"市值({rt}) < 退市线({t['mv_delist']})"
        elif rt < t["mv_delist"] * 1.5:
            if result["risk"] == "low":
                result["risk"] = "medium"
            result["details"]["trigger_mv"] = f"市值({rt}) 逼近退市线({t['mv_delist']})"

    return result


# ── E2: 监管处罚核查 ──────────────────────────────
# 双窗口策略 + 主体加权 + 频次增强（代码核查，非 LLM 筛选）

# 单条严重程度映射表
_REASON_SEVERITY = {
    "财务造假": 3, "虚假陈述": 3, "信息披露违规": 3,
    "违规担保": 3, "占用资金": 3, "侵犯商业秘密": 3,
    "内幕交易": 2, "市场操纵": 2, "违规减持": 2,
}

# 频次计数的事件类型白名单
_FREQ_EVENT_TYPES = {"警示", "问讯", "监管关注", "监管函", "警示函"}

# 频次计数的处罚机关白名单
_FREQ_ISSUERS = {"上交所", "深交所", "北交所", "证监会", "地方证监局"}

# 主体权重
_SUBJECT_WEIGHT = {"company": 1.0, "shareholder": 0.5, "officer": 0.5}

# 频次等级阈值（基于加权条数）
_FREQ_THRESHOLDS = [(5.0, "极高"), (3.0, "高"), (2.0, "中")]


def _e2_penalty_check(penalties_data: dict) -> dict:
    """E2 监管处罚核查 — 双窗口 + 主体加权 + 频次增强。

    输入：data_package.stock.penalties（中间层 get_regulatory_penalties 返回）
    输出：E2 综合等级 + 分窗口明细
    """
    records = penalties_data.get("data", [])
    result = {
        "risk": "low",
        "details": {
            "total_records": len(records),
            "window_a_count": 0,
            "window_a_max_severity": 0,
            "window_a_label": "无",
            "window_b_raw": 0,
            "window_b_weighted": 0.0,
            "window_b_label": "低",
            "combined_label": "低",
            "note": "",
        },
    }

    if not records:
        result["details"]["note"] = "无处罚记录"
        return result

    today = datetime.now()
    this_year = today.year

    # 窗口定义
    win_a_start = f"{this_year - 1}-01-01"
    win_a_end = f"{this_year - 1}-12-31"
    win_b_start = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    win_b_end = today.strftime("%Y-%m-%d")

    # ── 窗口 A：单条严重程度（仅 e2_countable 的记录）──
    win_a = [r for r in records
             if r.get("ann_date") and win_a_start <= r["ann_date"] <= win_a_end
             and r.get("e2_countable", False)]
    result["details"]["window_a_count"] = len(win_a)

    if win_a:
        severities = []
        for r in win_a:
            reason = r.get("reason_normalized", "unknown")
            sev = _REASON_SEVERITY.get(reason, 1)
            severities.append((reason, sev))
        max_sev = max(s for _, s in severities)
        result["details"]["window_a_max_severity"] = max_sev
        result["details"]["window_a_max_reasons"] = [
            reason for reason, s in severities if s == max_sev
        ][:3]
        result["details"]["window_a_label"] = _sev_to_label(max_sev)

    # ── 窗口 B：频次加权 ──
    win_b = [r for r in records
             if r.get("ann_date") and win_b_start <= r["ann_date"] <= win_b_end
             and r.get("e2_countable", False)]
    result["details"]["window_b_raw"] = len(win_b)

    if win_b:
        # 按事件类型或处罚机关过滤
        freq_pool = [
            r for r in win_b
            if r.get("event_type") in _FREQ_EVENT_TYPES
            or r.get("issuer_normalized") in _FREQ_ISSUERS
        ]
        # 主体加权
        weighted = sum(
            _SUBJECT_WEIGHT.get(r.get("subject_normalized", "company"), 1.0)
            for r in freq_pool
        )
        # 取一位小数
        weighted = round(weighted, 1)
        result["details"]["window_b_weighted"] = weighted
        result["details"]["window_b_breakdown"] = {
            "company": sum(1 for r in freq_pool if r.get("subject_normalized") == "company"),
            "officer": sum(1 for r in freq_pool if r.get("subject_normalized") == "officer"),
            "shareholder": sum(1 for r in freq_pool if r.get("subject_normalized") == "shareholder"),
        }
        # 频次等级
        for threshold, label in _FREQ_THRESHOLDS:
            if weighted >= threshold:
                result["details"]["window_b_label"] = label
                break

    # ── E2 综合 ──
    e2_single_sev = result["details"]["window_a_max_severity"]
    e2_freq_label = result["details"]["window_b_label"]

    # 频次→数值映射用于 max 比较
    _label_to_num = {"极高": 4, "高": 3, "中": 2, "低": 1}
    freq_num = _label_to_num.get(e2_freq_label, 1)
    combined_num = max(e2_single_sev, freq_num)

    # 叠加加成：频次≥高 且 单条≥高 → 直升极高
    if freq_num >= 3 and e2_single_sev >= 3:
        combined_num = 4
        result["details"]["note"] = "叠加加成：频次和单条均≥高，直升极高"

    result["details"]["combined_label"] = _sev_to_label(combined_num)

    # 风险等级映射
    risk_map = {4: "high", 3: "high", 2: "medium", 1: "low"}
    result["risk"] = risk_map.get(combined_num, "low")

    # 证据不属于预测项，不参与预测可信度
    result["confidence"] = "factual"

    return result


def _sev_to_label(sev: int) -> str:
    return {4: "极高", 3: "高", 2: "中", 1: "低"}.get(sev, "低")


# ── 维度汇总（仅统计，不裁决） ──────────────────────
# ⛔ Agent H 负责跨维度综合判定，脚本只输出各维度独立评估结果
def _dimension_summary(r1: dict, r2: dict, r4: dict, e2: dict, e3: dict) -> dict:
    """汇总各维度风险等级，不做加权合成"""
    risks = {"high": 3, "medium": 2, "low": 1, "data_insufficient": 0}
    scores = [risks.get(r["risk"], 0) for r in [r1, r2, r4, e2, e3]]
    return {
        "r1_risk": r1["risk"],
        "r2_risk": r2["risk"],
        "r4_risk": r4["risk"],
        "e2_risk": e2["risk"],
        "e3_risk": e3["risk"],
        "high_count": sum(1 for s in scores if s == 3),
        "medium_count": sum(1 for s in scores if s == 2),
        "insufficient_count": sum(1 for s in scores if s == 0),
    }


# ── 工具函数 ───────────────────────────────────────
def _parse_num(val):
    """安全解析数值"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if not isinstance(val, bool) else None
    if isinstance(val, bool):
        return None
    if isinstance(val, str):
        val = val.strip()
        if not val or val in ("--", "-", "None", ""):
            return None
        try:
            return float(val.replace(",", "").replace("亿", "e8").replace("万", "e4"))
        except ValueError:
            return None
    return None


def _load_input(args: list[str]) -> dict:
    """从 stdin 或 --input 加载输入 JSON"""
    if len(args) >= 2 and args[1].startswith("--input"):
        path = args[1].split("=", 1)[-1] if "=" in args[1] else args[2]
        return json.loads(Path(path).read_text())
    return json.load(sys.stdin)


# ── 主入口 ─────────────────────────────────────────
def main():
    try:
        inp = _load_input(sys.argv)
    except (json.JSONDecodeError, FileNotFoundError, IndexError) as e:
        print(json.dumps({"error": f"输入解析失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    ts_code = inp.get("ts_code", "")
    if not ts_code:
        print(json.dumps({"error": "缺少 ts_code"}, ensure_ascii=False))
        sys.exit(1)

    board = _classify_board(ts_code)
    t = THRESHOLDS.get(board, THRESHOLDS["主板"])

    fin = inp.get("financial", {})
    price = inp.get("price", {})
    penalties = inp.get("penalties", {})

    r1 = _r1_revenue_profit(fin, board, t)
    r2 = _r2_equity(fin, board, t, r1)
    r4 = _r4_consecutive_loss(fin, board, t, r1)
    e2 = _e2_penalty_check(penalties)
    e3 = _e3_trading_alert(price, board, t)

    overall = _dimension_summary(r1, r2, r4, e2, e3)

    output = {
        "ts_code": ts_code,
        "board": board,
        "thresholds": {
            "revenue_threshold": t["revenue"],
            "mv_delist": t["mv_delist"],
        },
        "r1_revenue_profit": r1,
        "r2_equity": r2,
        "r4_consecutive_loss": r4,
        "e2_penalty_check": e2,
        "e3_trading_alert": e3,
        "dimensions": overall,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
