#!/usr/bin/env python3
"""
market_scan.py — 全市场一键扫描

按中间层调用规则（同源≤2、异源并发、间隔sleep）批量拉取 10 个函数，
结果写入 /tmp/market_snapshot.json。

用法:
  python3 scripts/market_scan.py           # 默认输出到 /tmp/market_snapshot.json
  python3 scripts/market_scan.py /tmp/out.json  # 指定输出路径

输出 JSON 结构:
  {
    "index_quotes": {...},
    "breadth": {...},
    "ebs": {...},
    "buffett": {...},
    "northbound": {...},
    "margin": {...},
    "industry_spot": {...},
    "industry_flow": {...},
    "concept_spot": {...},
    "concept_flow": {...}
  }
"""

import json
import sys
import time
import random

OUTPUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/market_snapshot.json"

from a_share_market_middleware.overall.index_quotes import get_index_quotes
from a_share_market_middleware.overall.market import (
    get_market_breadth, get_ebs,
    get_buffett_index, get_northbound_flow, get_margin_summary,
)
from a_share_market_middleware.sector.board import get_board_spot, get_board_fund_flow
from a_share_market_middleware.sector.concept import get_concept_spot

results = {}

# ── Batch 1: 不同源，全并发 ──
r1 = get_index_quotes()
r2 = get_market_breadth()
r3 = get_margin_summary()
results.update(index_quotes=r1, breadth=r2, margin=r3)
time.sleep(random.uniform(1, 2))

# ── Batch 2: legulegu (ebs) + northbound ──
r4 = get_ebs()
r5 = get_northbound_flow()
results.update(ebs=r4, northbound=r5)
time.sleep(random.uniform(1, 2))

# ── Batch 3: buffett + PAE industry spot ──
r6 = get_buffett_index()
r7 = get_board_spot("industry")
results.update(buffett=r6, industry_spot=r7)
time.sleep(random.uniform(1, 2))

# ── Batch 4: PAE (max 2 concurrent): industry flow + concept spot ──
r8 = get_board_fund_flow("industry")
r9 = get_concept_spot()
results.update(industry_flow=r8, concept_spot=r9)
time.sleep(random.uniform(1, 2))

# ── Batch 5: PAE concept flow (single) ──
r10 = get_board_fund_flow("concept")
results["concept_flow"] = r10

# ── Verify ──
ok = sum(1 for v in results.values() if v.get("success"))
total = len(results)
print(f"Scan complete: {ok}/{total} succeeded")

# ── Write ──
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"Written to {OUTPUT}")
