#!/usr/bin/env python3
"""盲测 Step3: 汇总 LLM 提取结果 → 逐项比对引擎裁决 → 统计一致率

用法: python scripts/blind_compare.py
前提: 已运行 blind_sample.py + 子Agent完成各批次提取
"""
import json, os, glob
from collections import defaultdict

# 收集所有批次提取结果
extracted = []
for bf in sorted(glob.glob('/tmp/blind_batch_*_extracted.json')):
    with open(bf, 'r', encoding='utf-8') as f:
        data = json.load(f)
    items = data if isinstance(data, list) else list(data.values())
    extracted.extend(items)
for bf in sorted(glob.glob('/tmp/blind_batch_*_result.json')):
    with open(bf, 'r', encoding='utf-8') as f:
        data = json.load(f)
    items = data if isinstance(data, list) else list(data.values())
    extracted.extend(items)

print(f"Total extracted: {len(extracted)}")

# 加载原始 batch 获取引擎裁决
with open('/tmp/blind_test_batch.json', 'r', encoding='utf-8') as f:
    original = json.load(f)
engine_map = {o['analysis_date']: o for o in original}

# 映射: XM operation → engine verdict
OP_MAP = {'减仓': '空仓', '加仓': '持股', '持有': '持股', '持股': '持股', '观望': '观望'}

stats = {'total': 0, 'op_match': 0, 'op_mismatch': 0, 'op_nocmp': 0}
per_year = defaultdict(lambda: {'total': 0, 'op_match': 0, 'op_total': 0})
comparisons = []

for e in extracted:
    ad = e.get('analysis_date', '')
    if ad not in engine_map: continue
    eng = engine_map[ad]
    xm_op = e.get('operation', '无')
    mapped = OP_MAP.get(xm_op)
    year = int(ad[:4])
    stats['total'] += 1
    per_year[year]['total'] += 1
    r = {'date': ad, 'year': year, 'xm_op': xm_op, 'eng_op': eng['verdict_main']}
    if mapped:
        per_year[year]['op_total'] += 1
        if mapped == eng['verdict_main']:
            stats['op_match'] += 1; per_year[year]['op_match'] += 1; r['match'] = True
        else:
            stats['op_mismatch'] += 1; r['match'] = False
    else:
        stats['op_nocmp'] += 1; r['match'] = None
    comparisons.append(r)

# 输出
cmp_total = stats['op_match'] + stats['op_mismatch']
rate = f"{stats['op_match']/cmp_total*100:.1f}%" if cmp_total > 0 else 'N/A'
print(f"\n=== v4.6.1 一致性测试 (LLM提取, {stats['total']}篇) ===")
print(f"操作维度一致: {stats['op_match']}/{cmp_total} = {rate}")
print(f"不可比对(无操作): {stats['op_nocmp']}")
print(f"\n按年:")
for year in sorted(per_year):
    py = per_year[year]
    yr_rate = f"{py['op_match']/py['op_total']*100:.0f}%" if py['op_total'] > 0 else 'N/A'
    print(f"  {year}: {py['total']}篇, 操作一致 {py['op_match']}/{py['op_total']} ({yr_rate})")

with open('/tmp/blind_compare_results.json', 'w', encoding='utf-8') as f:
    json.dump({'stats': {k: dict(v) if isinstance(v, defaultdict) else v for k, v in stats.items()},
               'per_year': {str(k): dict(v) for k, v in per_year.items()}}, f, ensure_ascii=False, indent=2)
print(f"\nSaved to /tmp/blind_compare_results.json")
