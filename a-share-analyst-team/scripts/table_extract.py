#!/usr/bin/env python3
"""
table_extract.py — 从 TextIn 解析的全量 MD 中提取财务预测表格

输入: full_parse.py 产出的 MD 文件（含 HTML table）
输出: JSON — 五张财务预测表，金额统一归一为万元，附带来源标签

五张表:
  - core: 预测指标简表（分析师核心观点）
  - balance: 资产负债表
  - cashflow: 现金流量表
  - income: 利润表
  - metrics: 主要财务指标表（衍生计算）

用法:
  python3 table_extract.py <doc.md> [--json] > output.json
"""

import sys
import re
import json
from pathlib import Path

# ── 表识别 ──────────────────────────────────────────────

TABLE_MAP = {
    # 核心预测表（多种标题变体）
    "预测指标": "core",
    "项目＼年度": "core",
    "项目/年度": "core",
    "项目\\年度": "core",
    "盈利预测": "core",
    # 各财务报表
    "资产负债表": "balance",
    "现金流量表": "cashflow",
    "利润表": "income",
    # 比率/指标表
    "主要财务指标": "_combined",
    "主要财务比率": "_combined",
    # 合并表（需拆分）——内部标记，不直接输出
    "财务报表": "_combined",
    "财务报表和主要财务比率": "_combined",
}

# 合并表的子表识别键 —— 在合并表中的 section header 行匹配
SUBTABLE_KEYS = {
    "利润表": "income",
    "资产负债表": "balance",
    "现金流量表": "cashflow",
    "主要财务比率": "metrics",
    "主要财务指标": "metrics",
    "成长能力": None,      # metrics 子节
    "获利能力": None,
    "偿债能力": None,
    "营运能力": None,
    "每股指标": None,
    "估值比率": None,
}

# 标签 → 单位覆盖（节级单位不适用时，用此表覆盖）
LABEL_UNIT_OVERRIDE = {
    # 估值倍数
    "P/E": "倍",
    "P/S": "倍",
    "P/B": "倍",
    "PE": "倍",
    "PS": "倍",
    "PB": "倍",
    # 周转率
    "总资产周转率": "次",
    "应收账款周转率": "次",
    "存货周转率": "次",
    "固定资产周转率": "次",
}

# ── 单位归一化 → 万元 ───────────────────────────────────

def parse_amount(value_str, unit_hint=""):
    """
    将金额字符串转为万元数值。识别以下模式：
      - 百万元 → ×100 → 万元
      - 亿元 → ×10000 → 万元
      - 万元 → ×1（保留）
      - 元／股 / 元 → 保留原值，单位标记"元"（不换算，每股数据不适用万元）
      - % → 保留百分比数值
      - 倍/次 → 保留原值
    返回 (float|str|None, "万元"|"%"|"倍"|"次"|"元"|None)
    """
    if not value_str or not value_str.strip():
        return None, None

    v = value_str.strip().replace(",", "").replace(" ", "")

    # 百分比
    if v.endswith("%"):
        try:
            return float(v[:-1]), "%"
        except ValueError:
            return v, None

    # 纯数字
    try:
        num = float(v)
    except ValueError:
        return v, None

    # 单位推断
    unit_lower = unit_hint.lower().replace("（", "(").replace("）", ")")

    # 每股数据（元／股）→ 不换算
    if "元／股" in unit_lower or "元/股" in unit_lower or "股" in unit_lower:
        return num, "元"
    if "倍" in unit_lower:
        return num, "倍"
    if "次" in unit_lower:
        return num, "次"

    # 裸"元"——在中文研报中只出现在每股数据，不换算
    if unit_lower.strip() == "元":
        return num, "元"

    # 金融金额 → 万元
    if "百万" in unit_lower:
        return num * 100, "万元"
    elif "亿" in unit_lower:
        return num * 10000, "万元"
    elif "万" in unit_lower:
        return num, "万元"
    elif "元" in unit_lower:
        # 纯"元"单位（非每股）→ 换算
        return num / 10000, "万元"
    else:
        # 无明确单位——保持原值
        return num, None


# ── HTML 表格解析 ────────────────────────────────────────

def extract_tables_from_md(md_text):
    """从 Markdown 中提取所有 HTML <table> 块"""
    # 匹配完整 <table>...</table>（跨行）
    tables = []
    pattern = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL | re.IGNORECASE)
    for match in pattern.finditer(md_text):
        tables.append(match.group(0))
    return tables


def parse_table_rows(table_html):
    """解析 HTML table 为行列表，每行是 [cell1, cell2, ...]"""
    rows = []
    # 匹配所有 <tr>...</tr>
    tr_pattern = re.compile(r'<tr>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)

    for tr_match in tr_pattern.finditer(table_html):
        cells = []
        for td_match in td_pattern.finditer(tr_match.group(1)):
            # 清理：去 HTML 标签、去首尾空白
            text = re.sub(r'<[^>]+>', '', td_match.group(1)).strip()
            cells.append(text)
        if cells:
            rows.append(cells)

    return rows


def is_grouping_header(cells):
    """判断是否为分组标题行（如'流动资产：'、'非流动负债：'，数据列为空）"""
    if len(cells) < 2:
        return False
    # 有行标签，但数据列全部为空
    data_cells = cells[1:]
    return all(not c or not c.strip() for c in data_cells)


def is_section_header(cells):
    """判断是否为节标题（如'成长性'、'盈利能力'）——在指标表中常见"""
    if len(cells) < 2:
        return False
    data_cells = cells[1:]
    return all(not c or not c.strip() for c in data_cells)


def extract_unit_from_label(label):
    """从行标签中提取单位信息，如'主营收入（百万元）' → '百万元'"""
    match = re.search(r'[（(]([^）)]+)[）)]', label)
    return match.group(1) if match else ""


def clean_label(label):
    """去掉行标签中的单位括号，如'主营收入（百万元）' → '主营收入'"""
    return re.sub(r'[（(][^）)]*[）)]', '', label).strip()


# ── 合并表拆分 ───────────────────────────────────────────

def split_combined_table(rows, source_title=""):
    """
    将合并表（如'财务报表（百万元）'含利润表+资产负债表，
    '主要财务比率'含指标+现金流量表）拆分为独立的子表。
    返回 [(sub_type, years, sub_rows)]。
    """
    if not rows:
        return []

    # 解析列头（年份列）
    header_row = rows[0]
    years = [c.strip() for c in header_row[1:] if c and c.strip()]

    # 推断默认初始类型
    default_type = None
    if "比率" in source_title or "指标" in source_title:
        default_type = "metrics"
    elif "财务报表" in source_title:
        default_type = None  # 等第一个子表标题

    sub_tables = []
    current_type = default_type
    current_rows = []

    def flush():
        nonlocal current_rows
        if current_type and current_rows:
            sub_tables.append((current_type, list(years), list(current_rows)))
        current_rows = []

    for i, row in enumerate(rows):
        if len(row) < 2:
            continue

        label = row[0].strip()
        data_cells = row[1:]

        # 跳过完全空行
        if not label and all(not c or not c.strip() for c in data_cells):
            continue

        # 跳过表头行（第一行）
        if i == 0:
            continue

        # 检查是否为子表标题（匹配 SUBTABLE_KEYS）
        matched_type = None
        for key, typ in SUBTABLE_KEYS.items():
            if label == key or label.startswith(key):
                matched_type = typ
                break

        if matched_type is not None:
            # 子表类型切换点 → flush 旧表（仅当类型不同时）
            if current_type != matched_type:
                flush()
                current_type = matched_type
            continue

        # 未匹配到 SUBTABLE_KEYS，但数据列全空 → 节标题（如成长能力/获利能力）
        # 不切换表，不 flush，仅跳过该行
        if label and all(not c or not c.strip() for c in data_cells):
            continue

        # 常规数据行
        current_rows.append(row)

    # flush 最后一个子表
    flush()
    return sub_tables


# ── 主提取逻辑 ───────────────────────────────────────────

def _extract_data_rows(rows, years, table_type, unit_default="百万元"):
    """
    从解析后的行列表中提取数据行。
    rows: 已去除表头行（即从第二行开始）
    years: 列名列表（如 ['2025A', '2026E', ...]）
    table_type: 'core'|'income'|'balance'|'cashflow'|'metrics'
    unit_default: 无明确单位时的默认单位（metrics 不用）
    返回 extracted_rows 列表。
    """
    extracted_rows = []
    current_section = None
    current_section_unit = ""

    for row in rows:
        if len(row) < 2:
            continue

        label = row[0].strip()
        data_cells = row[1:]

        # 跳过完全空行
        if not label and all(not c or not c.strip() for c in data_cells):
            continue

        # 判分组标题 / 节标题
        if is_grouping_header(row):
            current_section = label.rstrip("：:")
            current_section_unit = extract_unit_from_label(label)
            continue

        if is_section_header(row) and label:
            current_section = label.rstrip("：:")
            current_section_unit = extract_unit_from_label(label)
            continue

        # 正常数据行
        unit_hint = extract_unit_from_label(label)
        label_clean = clean_label(label)

        if not unit_hint and current_section_unit:
            unit_hint = current_section_unit

        if label_clean in LABEL_UNIT_OVERRIDE:
            unit_hint = LABEL_UNIT_OVERRIDE[label_clean]

        values = {}
        for j, cell in enumerate(data_cells):
            if j < len(years):
                year = years[j]
                val_str = cell.strip()
                if table_type == "metrics":
                    val, unit = parse_amount(val_str, unit_hint)
                else:
                    if not unit_hint:
                        unit_hint = unit_default
                    val, unit = parse_amount(val_str, unit_hint)

                values[year] = {"raw": val_str, "value": val, "unit": unit}

        extracted_rows.append({
            "label": label_clean,
            "section": current_section,
            "unit_hint": unit_hint,
            "values": values,
        })

    return extracted_rows


def extract_financial_tables(md_text):
    """
    主函数：提取五张财务预测表
    返回 {
        "tables": {
            "core": [{rows}],
            "balance": [...],
            ...
        },
        "meta": {...}
    }
    """
    tables = extract_tables_from_md(md_text)
    result = {"tables": {}, "meta": {"source": "", "total_tables_found": len(tables)}}

    for table_html in tables:
        rows = parse_table_rows(table_html)
        if not rows:
            continue

        # 识别表类型（看第一行第一列）
        first_cell = rows[0][0] if rows[0] else ""
        table_type = None
        for key, typ in TABLE_MAP.items():
            if key in first_cell:
                table_type = typ
                break

        if table_type is None:
            continue

        # ── 合并表拆分 ──
        if table_type == "_combined":
            sub_tables = split_combined_table(rows, first_cell)
            for sub_type, years, sub_rows in sub_tables:
                if not sub_type:
                    continue
                extracted_rows = _extract_data_rows(sub_rows, years, sub_type)
                if extracted_rows:
                    result["tables"][sub_type] = {
                        "title": f"{first_cell} › {sub_type}",
                        "years": years,
                        "rows": extracted_rows,
                        "row_count": len(extracted_rows),
                    }
            continue

        # ── 普通表处理 ──
        header_row = rows[0]
        years = [c.strip() for c in header_row[1:] if c and c.strip()]
        data_rows = rows[1:]  # 去除表头行
        extracted_rows = _extract_data_rows(data_rows, years, table_type)

        if extracted_rows:
            result["tables"][table_type] = {
                "title": first_cell.strip(),
                "years": years,
                "rows": extracted_rows,
                "row_count": len(extracted_rows),
            }

    return result


# ── CLI ──────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python3 table_extract.py <doc.md>", file=sys.stderr)
        sys.exit(1)

    md_path = sys.argv[1]
    md_text = Path(md_path).read_text(encoding="utf-8")

    result = extract_financial_tables(md_text)
    result["meta"]["source"] = md_path
    result["meta"]["tables_extracted"] = list(result["tables"].keys())

    if "--json" in sys.argv or True:  # 默认 JSON 输出
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 人类可读摘要
        for tname, tdata in result["tables"].items():
            print(f"\n{'='*60}")
            print(f"  {tdata['title']} ({tdata['row_count']} 行)")
            print(f"  年份: {', '.join(tdata['years'])}")
            print(f"{'-'*60}")
            for r in tdata["rows"][:5]:
                vals = ", ".join(
                    f"{y}={v['raw']}" for y, v in r["values"].items()
                )
                print(f"  {r['label']}: {vals}")
            if tdata["row_count"] > 5:
                print(f"  ... 还有 {tdata['row_count']-5} 行")


if __name__ == "__main__":
    main()
