#!/usr/bin/env python3
"""
报告摘要提取器 —— 从上游 Agent 报告中提取关键段落，供主 Agent 构造 F 的精简 context。

用法：
  python3 plan_report.py <report_path> --target "裁决结论+关键分歧+评级"
  python3 plan_report.py <report_path> --target "催化剂矩阵+时间窗口"

输出到 stdout：纯文本摘要。
"""

import sys
import re
import json
import argparse
from pathlib import Path


# 各报告类型的摘要提取配置
EXTRACTION_RULES = {
    "B3": {
        "headers": ["裁决", "结论", "评级", "分歧", "对比"],
        "max_lines": 30,
    },
    "C3": {
        "headers": ["裁决", "结论", "分歧", "趋势判断"],
        "max_lines": 25,
    },
    "E": {
        "headers": ["催化剂", "时间窗口", "操作建议", "信号", "评分"],
        "max_lines": 30,
    },
    "H": {
        "headers": ["红线", "偏差", "风控", "纠正"],
        "max_lines": 25,
    },
    "I": {
        "headers": ["违规", "不一致", "问题", "数据差异", "合规"],
        "max_lines": 20,
    },
}


def identify_report_type(path: str) -> str:
    """根据文件名推断报告类型"""
    filename = Path(path).name.lower()
    for rtype in ["B3", "C3", "E", "H", "I"]:
        if rtype.lower() in filename:
            return rtype
    return None


def extract_section(text: str, keywords: list[str], max_lines: int) -> str:
    """
    提取包含关键字的段落。策略：
    1. 找到所有包含任意关键字的行
    2. 取每行的上下文（前后各 2 行）
    3. 去重、合并相邻块
    4. 截断到 max_lines
    """
    lines = text.split("\n")
    matched_indices = set()

    for i, line in enumerate(lines):
        for kw in keywords:
            if kw.lower() in line.lower():
                # 取前后各 2 行
                for j in range(max(0, i - 2), min(len(lines), i + 3)):
                    matched_indices.add(j)
                break

    if not matched_indices:
        # 无匹配 → 返回全文前 max_lines 行
        return "\n".join(lines[:max_lines])

    # 合并相邻块：取最小到最大的连续区间
    sorted_idx = sorted(matched_indices)
    result_lines = []
    last_idx = sorted_idx[0] - 2

    for idx in sorted_idx:
        if idx > last_idx + 3:
            result_lines.append("---")
        result_lines.append(lines[idx])
        last_idx = idx

    result = "\n".join(result_lines)

    # 截断
    result_lines = result.split("\n")
    if len(result_lines) > max_lines:
        result = "\n".join(result_lines[:max_lines]) + "\n[...截断]"

    return result


def main():
    parser = argparse.ArgumentParser(description="从 Agent 报告中提取关键段落摘要")
    parser.add_argument("report_path", help="上游 Agent 报告路径")
    parser.add_argument(
        "--target",
        default=None,
        help="提取目标描述（如 '裁决结论+关键分歧+评级'）。不指定时自动检测报告类型。",
    )
    parser.add_argument(
        "--report-type",
        default=None,
        choices=["B3", "C3", "E", "H", "I"],
        help="手动指定报告类型",
    )
    args = parser.parse_args()

    report_path = Path(args.report_path)
    if not report_path.exists():
        print(f"ERROR: 文件不存在: {report_path}", file=sys.stderr)
        sys.exit(1)

    text = report_path.read_text(encoding="utf-8")

    # 确定报告类型
    rtype = args.report_type or identify_report_type(str(report_path))
    if rtype is None:
        # 无法识别类型 → 返回前 20 行
        lines = text.split("\n")
        print("\n".join(lines[:20]))
        print("\n[...无法识别报告类型，已截断]")
        return

    # 确定关键字
    if args.target:
        # 从 target 字符串提取关键字
        keywords = re.split(r"[+、,，\s]+", args.target)
    else:
        rules = EXTRACTION_RULES.get(rtype, {})
        keywords = rules.get("headers", [])

    rules = EXTRACTION_RULES.get(rtype, {})
    max_lines = rules.get("max_lines", 25)

    result = extract_section(text, keywords, max_lines)
    print(result)


if __name__ == "__main__":
    main()
