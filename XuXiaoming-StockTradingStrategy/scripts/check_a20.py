#!/usr/bin/env python3
"""A20 合规扫描——检查报告一~八节是否包含博客引用。

用法:
    python scripts/check_a20.py reports/2026-07-17_*.md
    python scripts/check_a20.py reports/*.md  # 批量扫描

规则:
    - 一~八节（第九节「博客对照」之前的所有内容）不得出现「徐小明」「博客」「博文」
    - 例外: 第七节标题「徐小明公众号风格」中的「徐小明」不算违规
    - 第九节（博客对照）中的引用不算违规
    - 历史方法论引用（如「趋势为王结构修边」）不算违规

检查项:
    1. 一~八节无博客关键词
    2. 震荡来路判断存在（来路/入震/退震）
    3. v4.6.23 关键术语存在（三合一≥2d/退震≥3d/退震未确认）
"""

import re
import sys
from pathlib import Path


def check_report(filepath: str) -> dict:
    path = Path(filepath)
    if not path.exists():
        return {"file": filepath, "error": "file not found"}

    content = path.read_text(encoding="utf-8")

    # Split into sections 1-8 and section 9
    sec9_match = re.search(r"## 九、博客对照", content)
    if sec9_match:
        body_1_8 = content[: sec9_match.start()]
        has_sec9 = True
    else:
        body_1_8 = content
        has_sec9 = False

    violations = []

    # Check 1: blog keywords in sections 1-8
    for label, pat in [("徐小明", "徐小明"), ("博客", "博客"), ("博文", "博文")]:
        for m in re.finditer(pat, body_1_8):
            line_start = body_1_8.rfind("\n", 0, m.start()) + 1
            line_end = body_1_8.find("\n", m.start())
            line = body_1_8[line_start:line_end if line_end > 0 else None]

            # Allow in section 7 title
            if "徐小明公众号风格" in line or "徐小明技术分析思想" in line:
                continue
            # Allow in section 9 header
            if "博客对照" in line:
                continue
            # Allow historical methodology references (not today's blog)
            if label == "徐小明" and any(
                kw in line
                for kw in ["风格", "历史", "原文", "方法论", "思想", "技术分析", "公众号"]
            ):
                continue

            violations.append(f"一~八节出现「{label}」: {line.strip()[:100]}")

    # Check 2: oscillation analysis presence
    osc_checks = {
        "来路判断": "来路" in body_1_8,
        "入震标准": "入震" in body_1_8,
        "退震状态": "退震" in body_1_8,
    }
    missing_osc = [k for k, v in osc_checks.items() if not v]

    # Check 3: v4.6.23 key terms
    v4623_terms = ["三合一≥2d", "退震≥3d", "退震未确认", "震荡来路判断"]
    v4623_present = [t for t in v4623_terms if t in body_1_8]
    v4623_missing = [t for t in v4623_terms if t not in body_1_8]
    # "退震分流" is optional (only needed when both origins present)
    if "退震分流" in v4623_missing:
        v4623_missing.remove("退震分流")

    # Check 4: five-index resonance table
    has_resonance_table = bool(re.search(r"五指数共振投票", body_1_8))

    # Check 5: NH/NL breadth
    has_breadth = "NH/NL" in body_1_8 or "CNHL" in body_1_8 or "HL_Ratio" in body_1_8

    # Check 6: minute structure
    has_minute = "分钟线" in body_1_8

    passed = (
        len(violations) == 0
        and len(missing_osc) == 0
        and len(v4623_missing) <= 1
    )

    return {
        "file": filepath,
        "passed": passed,
        "a20_violations": violations,
        "missing_osc": missing_osc,
        "v4623_missing": v4623_missing,
        "has_sec9": has_sec9,
        "has_resonance_table": has_resonance_table,
        "has_breadth": has_breadth,
        "has_minute": has_minute,
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/check_a20.py <report.md> [report2.md ...]")
        sys.exit(1)

    all_passed = True
    for fp in sys.argv[1:]:
        result = check_report(fp)
        print(f"\n{'='*60}")
        print(f"A20 Scan: {result['file']}")
        print(f"{'='*60}")

        if "error" in result:
            print(f"  ❌ {result['error']}")
            all_passed = False
            continue

        if result["a20_violations"]:
            print(f"  ❌ A20违规: {len(result['a20_violations'])}处")
            for v in result["a20_violations"]:
                print(f"     → {v}")
            all_passed = False
        else:
            print(f"  ✅ 一~八节无博客引用")

        if result["missing_osc"]:
            print(f"  ⚠️ 震荡来路不完整: {', '.join(result['missing_osc'])}")
            all_passed = False
        else:
            print(f"  ✅ 震荡来路判断完整")

        if result["v4623_missing"]:
            print(
                f"  ⚠️ v4.6.23术语缺失: {', '.join(result['v4623_missing'])}"
            )
        else:
            print(f"  ✅ v4.6.23术语完整")

        for check, label in [
            ("has_sec9", "第九节博客对照"),
            ("has_resonance_table", "五指数共振投票表"),
            ("has_breadth", "NH/NL广度分析"),
            ("has_minute", "分钟线分析"),
        ]:
            status = "✅" if result[check] else "⚠️ 缺失"
            print(f"  {status} {label}")

        print()

    if all_passed:
        print("全部通过 ✅")
    else:
        print("存在问题 ⚠️")
        sys.exit(1)


if __name__ == "__main__":
    main()
