#!/usr/bin/env python3
"""
search_ipo.py — 按企业名搜索 IPO 进度

同时搜索三个 EM 全量表（辅导备案/申报队列/上会审核），
推断企业所处的 IPO 阶段，如有股票代码则查发行详情。

用法:
    python3 search_ipo.py --name "宇树科技"
    python3 search_ipo.py --name "燧原" --json    # JSON 输出
"""

import argparse
import json
import sys
import re
import pandas as pd
import akshare as ak


# ── 名称标准化 ──────────────────────────────────
def _normalize(name: str) -> str:
    """去掉常见后缀，用于模糊匹配"""
    suffixes = [
        "股份有限公司", "有限公司", "有限责任公司",
        "股份公司", "集团公司", "（特殊普通合伙）",
        "(特殊普通合伙)", "（有限合伙）", "(有限合伙)",
    ]
    for s in suffixes:
        name = name.replace(s, "")
    return name.strip()


def _fuzzy_match(df: pd.DataFrame, col: str, query: str) -> pd.DataFrame:
    """DataFrame 中某列模糊匹配 query，返回匹配行"""
    if df.empty:
        return df
    norm_query = _normalize(query)
    # 先完全匹配
    mask = df[col].str.contains(query, na=False, regex=False)
    if not mask.any():
        # 标准化后匹配
        norm_col = df[col].apply(lambda x: _normalize(str(x)))
        mask = norm_col.str.contains(norm_query, na=False, regex=False)
    return df[mask]


def _infer_market(code: str) -> str:
    """按股票代码推断上市地"""
    if not code or not re.match(r"^\d{6}$", str(code)):
        return None
    code = str(code)
    if code.startswith("9") or code.startswith("8"):
        return "北交所"
    if code.startswith("688"):
        return "上交所科创板"
    if code.startswith("3"):
        return "深交所创业板"
    if code.startswith("0") or code.startswith("2"):
        return "深交所主板"
    if code.startswith("6"):
        return "上交所主板"
    return None


# ── 阶段搜索 ────────────────────────────────────
def search(name: str) -> dict:
    """搜索企业 IPO 进度，返回结构化结果"""
    result = {
        "query": name,
        "found": False,
        "stage": "未查询到",
        "tutor": None,       # 辅导备案
        "declare": None,     # 申报队列
        "review": None,      # 上会审核
        "ipo_summary": None, # 发行摘要
        "ipo_detail": None,  # 发行详情
    }

    # ── 代码直查：输入为 6 位数字时，直调 ④⑤ ──
    if re.match(r"^\d{6}$", name):
        for code in [name]:
            try:
                df_summary = ak.stock_ipo_summary_cninfo(code)
                if not df_summary.empty:
                    row = df_summary.iloc[0].to_dict()
                    result["ipo_summary"] = {
                        "股票代码": row.get("股票代码"),
                        "发行价格": row.get("发行价格"),
                        "总发行数量": row.get("总发行数量"),
                        "每股面值": row.get("每股面值"),
                        "发行市盈率": row.get("摊薄发行市盈率") or row.get("发行市盈率"),
                        "发行前每股净资产": row.get("发行前每股净资产"),
                        "发行后每股净资产": row.get("发行后每股净资产"),
                        "募集资金净额": row.get("募集资金净额"),
                        "上网发行中签率": row.get("上网发行中签率"),
                        "招股公告日期": str(row.get("招股公告日期", ""))[:10] if pd.notna(row.get("招股公告日期")) else None,
                        "上网发行日期": str(row.get("上网发行日期", ""))[:10] if pd.notna(row.get("上网发行日期")) else None,
                        "上市日期": str(row.get("上市日期", ""))[:10] if pd.notna(row.get("上市日期")) else None,
                        "主承销商": row.get("主承销商"),
                        "发行费用总额": row.get("发行费用总额"),
                    }
            except Exception:
                pass
            try:
                df_info = ak.stock_ipo_info(code)
                if not df_info.empty:
                    detail = {}
                    for _, r in df_info.iterrows():
                        detail[r["item"]] = r["value"]
                    result["ipo_detail"] = detail
            except Exception:
                pass
        if result["ipo_summary"] or result["ipo_detail"]:
            result["found"] = True
            result["stage"] = "已上市/已注册"
        return result

    # ① 辅导备案
    try:
        df_tutor = ak.stock_ipo_tutor_em()
        match = _fuzzy_match(df_tutor, "企业名称", name)
        if not match.empty:
            row = match.iloc[0].to_dict()
            result["tutor"] = {
                "企业名称": row.get("企业名称"),
                "辅导机构": row.get("辅导机构"),
                "辅导状态": row.get("辅导状态"),
                "报告类型": row.get("报告类型"),
                "派出机构": row.get("派出机构"),
                "备案日期": str(row.get("备案日期", ""))[:10],
                "报告标题": row.get("报告标题"),
            }
    except Exception as e:
        result["tutor"] = {"error": str(e)}

    # ② 申报队列
    try:
        df_declare = ak.stock_ipo_declare_em()
        match = _fuzzy_match(df_declare, "企业名称", name)
        if not match.empty:
            row = match.iloc[0].to_dict()
            result["declare"] = {
                "企业名称": row.get("企业名称"),
                "最新状态": row.get("最新状态"),
                "注册地": row.get("注册地"),
                "保荐机构": row.get("保荐机构"),
                "律师事务所": row.get("律师事务所"),
                "会计师事务所": row.get("会计师事务所"),
                "拟上市地点": row.get("拟上市地点"),
                "更新日期": str(row.get("更新日期", ""))[:10],
                "招股说明书": row.get("招股说明书"),
            }
    except Exception as e:
        result["declare"] = {"error": str(e)}

    # ③ 上会审核
    stock_code = None
    try:
        df_review = ak.stock_ipo_review_em()
        match = _fuzzy_match(df_review, "企业名称", name)
        if not match.empty:
            row = match.iloc[0].to_dict()
            stock_code = row.get("股票代码")
            # 过滤非空股票代码（注册成功后才有）
            if stock_code and isinstance(stock_code, str):
                stock_code = stock_code.strip()
                if stock_code in ("", "nan", "NaN", "None"):
                    stock_code = None
            result["review"] = {
                "企业名称": row.get("企业名称"),
                "股票简称": row.get("股票简称"),
                "股票代码": stock_code,
                "上市板块": row.get("上市板块"),
                "上会日期": str(row.get("上会日期", ""))[:10] if pd.notna(row.get("上会日期")) else None,
                "审核状态": row.get("审核状态"),
                "发审委委员": row.get("发审委委员"),
                "主承销商": row.get("主承销商"),
                "发行数量(股)": row.get("发行数量(股)"),
                "拟融资额(元)": row.get("拟融资额(元)"),
                "公告日期": str(row.get("公告日期", ""))[:10] if pd.notna(row.get("公告日期")) else None,
                "上市日期": str(row.get("上市日期", ""))[:10] if pd.notna(row.get("上市日期")) else None,
            }
    except Exception as e:
        result["review"] = {"error": str(e)}

    # ④ + ⑤ 如果有代码，查发行详情
    if stock_code:
        # 代码可能带后缀如 "A26003"，需提取 6 位纯数字
        pure_code = re.search(r"\d{6}", str(stock_code))
        if pure_code:
            code = pure_code.group()
            try:
                df_summary = ak.stock_ipo_summary_cninfo(code)
                if not df_summary.empty:
                    row = df_summary.iloc[0].to_dict()
                    result["ipo_summary"] = {
                        "股票代码": row.get("股票代码"),
                        "发行价格": row.get("发行价格"),
                        "总发行数量": row.get("总发行数量"),
                        "每股面值": row.get("每股面值"),
                        "发行市盈率": row.get("摊薄发行市盈率") or row.get("发行市盈率"),
                        "发行前每股净资产": row.get("发行前每股净资产"),
                        "发行后每股净资产": row.get("发行后每股净资产"),
                        "募集资金净额": row.get("募集资金净额"),
                        "上网发行中签率": row.get("上网发行中签率"),
                        "招股公告日期": str(row.get("招股公告日期", ""))[:10] if pd.notna(row.get("招股公告日期")) else None,
                        "上网发行日期": str(row.get("上网发行日期", ""))[:10] if pd.notna(row.get("上网发行日期")) else None,
                        "上市日期": str(row.get("上市日期", ""))[:10] if pd.notna(row.get("上市日期")) else None,
                        "主承销商": row.get("主承销商"),
                        "发行费用总额": row.get("发行费用总额"),
                    }
            except Exception:
                pass

            try:
                df_info = ak.stock_ipo_info(code)
                if not df_info.empty:
                    detail = {}
                    for _, r in df_info.iterrows():
                        detail[r["item"]] = r["value"]
                    result["ipo_detail"] = detail
            except Exception:
                pass

    # ── 名称一致性验证 ──
    name_sources = {}
    if result["tutor"] and not result["tutor"].get("error"):
        name_sources["辅导备案表"] = result["tutor"].get("企业名称")
    if result["declare"] and not result["declare"].get("error"):
        name_sources["申报队列表"] = result["declare"].get("企业名称")
    if result["review"] and not result["review"].get("error"):
        name_sources["上会审核表"] = result["review"].get("企业名称")
    if result["review"] and result["review"].get("股票简称"):
        name_sources["股票简称"] = result["review"].get("股票简称")
    if result["ipo_summary"]:
        # ④⑤ 不含企业全称字段，不参与名称比对
        pass

    # 去重比对（仅比较全称，股票简称单独标出）
    full_names = set()
    short_name = result.get("review", {}).get("股票简称") if result.get("review") else None
    for src, nm in name_sources.items():
        if nm and isinstance(nm, str) and len(nm) > 2 and "简称" not in src:
            full_names.add(nm)

    nv = {}
    if short_name and short_name not in [fn.split("股份")[0] if "股份" in fn else fn[:4] for fn in full_names]:
        nv["short_name"] = short_name
        nv["short_name_note"] = "股票简称（可能与全称不同，属正常现象）"

    if len(full_names) > 1:
        nv["consistent"] = False
        nv["note"] = "不同来源的 IPO 全称不一致，可能上市后更名"
        # 带来源标注的名称列表（同名合并来源）
        name_source_map = {}
        for src, nm in name_sources.items():
            if nm and isinstance(nm, str) and len(nm) > 2 and "简称" not in src:
                if nm not in name_source_map:
                    name_source_map[nm] = []
                name_source_map[nm].append(src)
        nv["names_with_source"] = [{"name": k, "source": "、".join(v)} for k, v in name_source_map.items()]
    elif len(full_names) == 1:
        nv["consistent"] = True
        nv["name"] = list(full_names)[0]

    if nv:
        result["name_verification"] = nv

    # ── 阶段推断 ──
    if result["ipo_summary"] or result["ipo_detail"]:
        result["found"] = True
        result["stage"] = "已上市/已注册"
    elif result["review"] and not result["review"].get("error"):
        declare_status = (result.get("declare") or {}).get("最新状态", "")
        if "注册" in str(declare_status):
            result["found"] = True
            result["stage"] = declare_status
        elif stock_code and re.match(r"^\d{6}$", str(stock_code)):
            result["found"] = True
            result["stage"] = "注册生效"
        else:
            result["found"] = True
            result["stage"] = "上会审核"
    elif result["declare"] and not result["declare"].get("error"):
        result["found"] = True
        result["stage"] = "申报队列"
    elif result["tutor"] and not result["tutor"].get("error"):
        result["found"] = True
        t = result["tutor"]
        rtype = t.get("报告类型", "")
        title = t.get("报告标题", "")
        phase_match = re.search(r"第([一二三四五六七八九十\d]+)期", str(title))
        phase_str = f"（{phase_match.group(0)}）" if phase_match else ""
        result["stage"] = "辅导备案"
        if "验收" in rtype:
            result["tutor"]["辅导状态"] = "辅导验收通过"
        elif "工作完成" in rtype:
            result["tutor"]["辅导状态"] = "辅导工作完成"
        elif "进展" in rtype:
            result["tutor"]["辅导状态"] = f"辅导中{phase_str}"
        else:
            result["tutor"]["辅导状态"] = "辅导中（首期）"

    # ── 交易所/板块提取（独立顶层字段）──
    exchange = None
    if result.get("review") and not result["review"].get("error"):
        exchange = result["review"].get("上市板块")
    if not exchange and result.get("declare") and not result["declare"].get("error"):
        exchange = result["declare"].get("拟上市地点")
    if not exchange and (result.get("ipo_summary") or result.get("ipo_detail")):
        exchange = _infer_market(stock_code) if stock_code else None
    if exchange:
        result["exchange"] = exchange

    return result


# ── JSON 序列化 ─────────────────────────────────
class _Encoder(json.JSONEncoder):
    def default(self, obj):
        if pd.isna(obj):
            return None
        if isinstance(obj, (pd.Timestamp,)):
            return str(obj)[:10]
        return str(obj)


# ── 命令行入口 ──────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="按企业名搜索 A 股 IPO 进度")
    parser.add_argument("--name", required=True, help="企业名称（支持模糊匹配）")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    result = search(args.name)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, cls=_Encoder))
    else:
        _print_human(result)


def _print_human(r: dict):
    """人类可读输出 — 全量结构化"""
    # ── 确定企业全称：取最近阶段表中的名称 ──
    full_name = None
    for key in ["review", "declare", "tutor"]:
        v = r.get(key)
        if v and not v.get("error") and v.get("企业名称"):
            full_name = v["企业名称"]
            break
    if not full_name and r.get("ipo_summary"):
        full_name = f"代码 {r['ipo_summary'].get('股票代码')}"
    if not full_name:
        full_name = r["query"]

    # 确定标题和代码简称
    code = None
    short_name = None
    for key in ["review"]:
        v = r.get(key)
        if v and not v.get("error"):
            c = v.get("股票代码")
            if c and re.match(r"^\d{6}$", str(c)):
                code = str(c)
                short_name = v.get("股票简称")
                break

    if code:
        title = f"{code}"
        if short_name:
            title += f"　{short_name}"
        if full_name:
            title = f"{full_name}　{title}"
        print(f"【{title}】")
    else:
        print(f"【{full_name}】")
    # 名称验证
    nv = r.get("name_verification")
    if nv:
        if not nv.get("consistent") and nv.get("names_with_source"):
            parts = []
            for item in nv["names_with_source"]:
                parts.append(f"{item['name']}（{item['source']}）")
            print(f"  ⚠️ 名称差异：{' vs '.join(parts)}")
    print(f"  阶段：{r['stage']}")
    if r.get("exchange"):
        print(f"  交易所/板块：{r['exchange']}")

    if not r["found"]:
        print(f"  未在 IPO 数据库中查询到该企业。")
        return

    # ═══════════════════════════════════════
    # 辅导阶段
    # ═══════════════════════════════════════
    if "辅导" in r["stage"] and "申报" not in r["stage"] and "上会" not in r["stage"] and "已上市" not in r["stage"]:
        t = r["tutor"]
        print(f"\n辅导信息")
        if t.get("报告类型"):
            print(f"  · 报告类型：{t['报告类型']}")
        print(f"  · 辅导机构：{t.get('辅导机构')}")
        print(f"  · 辅导状态：{t.get('辅导状态')}")
        print(f"  · 派出机构：{t.get('派出机构')}")
        print(f"  · 备案日期：{t.get('备案日期')}")
        return

    # ═══════════════════════════════════════
    # 申报阶段
    # ═══════════════════════════════════════
    if r["stage"].startswith("申报队列"):
        d = r["declare"]
        print(f"\n申报信息")
        print(f"  · 最新状态：{d.get('最新状态')}")
        print(f"  · 拟上市地点：{d.get('拟上市地点')}")
        print(f"  · 注册地：{d.get('注册地')}")
        print(f"  · 更新日期：{d.get('更新日期')}")
        print(f"\n中介机构")
        print(f"  · 保荐机构：{d.get('保荐机构')}")
        print(f"  · 律师事务所：{d.get('律师事务所')}")
        print(f"  · 会计师事务所：{d.get('会计师事务所')}")
        if d.get("招股说明书"):
            print(f"\n招股说明书")
            print(f"  · {d.get('招股说明书')}")
        return

    # ═══════════════════════════════════════
    # 上会审核 / 注册生效 / 已上市 阶段
    # ═══════════════════════════════════════
    if "上会" in r["stage"] or "注册" in r["stage"] or "已上市" in r["stage"]:
        v = r["review"]
        if not v or v.get("error"):
            return

        is_listed = "已上市" in r["stage"] or r.get("ipo_summary")

        if is_listed:
            # ── 已上市：精简头信息 ──
            print(f"\n基本信息")
            market = _infer_market(code) if code else None
            if market:
                print(f"  · 上市地：{market}")
            d_for_loc = r.get("declare")
            if d_for_loc and not d_for_loc.get("error") and d_for_loc.get("注册地"):
                print(f"  · 注册地：{d_for_loc.get('注册地')}")
            if v.get("上市日期"):
                print(f"  · 上市日期：{v['上市日期']}")
        else:
            # ── 上会审核/注册阶段：展示审核信息 ──
            print(f"\n审核信息")
            sd = v.get('上会日期')
            print(f"  · 上会日期：{'待定' if not sd or sd in ('NaT', 'nan', 'None', '') else sd}")
            print(f"  · 审核状态：{v.get('审核状态')}")
            print(f"  · 上市板块：{v.get('上市板块')}")
            # 注册地（公司信息，来自申报表）
            d_for_loc = r.get("declare")
            if d_for_loc and not d_for_loc.get("error") and d_for_loc.get("注册地"):
                print(f"  · 注册地：{d_for_loc.get('注册地')}")
            if v.get("股票代码") and re.match(r"^\d{6}$", str(v["股票代码"])):
                print(f"  · 股票代码：{v['股票代码']}　{v.get('股票简称', '')}")
            elif v.get("股票代码"):
                print(f"  · 股票代码：尚未取得正式股票代码")
            print(f"  · 主承销商：{v.get('主承销商')}")
            if v.get("发行数量(股)"):
                wan = int(v["发行数量(股)"]) / 10000
                print(f"  · 拟发行：{wan:.0f} 万股")
            if v.get("拟融资额(元)") and float(v["拟融资额(元)"]) > 0:
                yi = float(v["拟融资额(元)"]) / 1e4  # 字段名"元"实际单位为万元
                print(f"  · 拟融资：{yi:.1f} 亿元")
            if v.get("发审委委员"):
                print(f"  · 发审委委员：{v['发审委委员']}")
            if v.get("上市日期"):
                print(f"  · 上市日期：{v['上市日期']}")

        # 中介机构（来自申报表）
        d = r.get("declare")
        if d and not d.get("error"):
            if d.get("保荐机构") or d.get("律师事务所") or d.get("会计师事务所"):
                print(f"\n中介机构")
                if d.get("保荐机构"):
                    print(f"  · 保荐机构：{d.get('保荐机构')}")
                if d.get("律师事务所"):
                    print(f"  · 律师事务所：{d.get('律师事务所')}")
                if d.get("会计师事务所"):
                    print(f"  · 会计师事务所：{d.get('会计师事务所')}")

    # ═══════════════════════════════════════
    # 发行信息（已上市）
    if r.get("ipo_summary"):
        s = r["ipo_summary"]
        print(f"\n发行信息")
        if s.get("发行价格"):
            print(f"  · 发行价格：{s['发行价格']} 元")
        if s.get("总发行数量"):
            print(f"  · 发行数量：{s['总发行数量']} 万股")
        if s.get("每股面值"):
            print(f"  · 每股面值：{s['每股面值']} 元")
        if s.get("发行市盈率") and str(s["发行市盈率"]) != "nan" and pd.notna(s.get("发行市盈率")):
            print(f"  · 发行市盈率：{s['发行市盈率']}")
        if s.get("发行前每股净资产") and str(s["发行前每股净资产"]) != "--":
            print(f"  · 发行前每股净资产：{s['发行前每股净资产']} 元")
        if s.get("发行后每股净资产") and str(s["发行后每股净资产"]) != "--":
            print(f"  · 发行后每股净资产：{s['发行后每股净资产']} 元")
        if s.get("上网发行中签率"):
            zql = float(s["上网发行中签率"]) if isinstance(s["上网发行中签率"], str) else s["上网发行中签率"]
            print(f"  · 中签率：{zql:.2f}%")
        if s.get("募集资金净额"):
            yi = float(s["募集资金净额"]) / 10000
            print(f"  · 募资净额：{yi:.1f} 亿元")
        if s.get("招股公告日期") and str(s["招股公告日期"]) != "NaT":
            print(f"  · 招股公告日期：{s['招股公告日期']}")
        if s.get("上网发行日期") and str(s["上网发行日期"]) != "NaT":
            print(f"  · 上网发行日期：{s['上网发行日期']}")
        if s.get("上市日期") and str(s["上市日期"]) != "NaT":
            print(f"  · 上市日期：{s['上市日期']}")

    if r.get("ipo_detail"):
        detail = r["ipo_detail"]
        # 代码推断上市地
        review_code = None
        if r.get("review") and not r["review"].get("error"):
            rc = r["review"].get("股票代码")
            if rc and re.match(r"^\d{6}$", str(rc)):
                review_code = str(rc)
        inferred_market = _infer_market(review_code) if review_code else None

        print(f"\nIPO 详情")
        for item, label in [
            ("上市地", "上市地"),
            ("承销方式", "承销方式"),
            ("上市推荐人", "上市推荐人"),
            ("发行方式", "发行方式"),
            ("首发前总股本（万股）", "首发前总股本"),
            ("首发后总股本（万股）", "首发后总股本"),
            ("实际发行量（万股）", "实际发行量"),
            ("预计募集资金（万元）", "预计募集资金"),
            ("实际募集资金合计（万元）", "实际募集资金合计"),
            ("发行费用总额（万元）", "发行费用总额"),
            ("承销费用（万元）", "承销费用"),
            ("募集资金净额（万元）", "募集资金净额"),
            ("招股公告日", "招股公告日"),
        ]:
            val = detail.get(item)
            # 上市地：优先用推断值
            if item == "上市地" and not val or str(val) in ("nan", "NaN", "--", ""):
                if inferred_market:
                    val = inferred_market
            if not val or str(val) in ("nan", "NaN", "--", ""):
                continue
            if "万元" in item:
                print(f"  · {label}：{val} 万元")
            elif "万股" in item:
                print(f"  · {label}：{val} 万股")
            else:
                print(f"  · {label}：{val}")


if __name__ == "__main__":
    main()
