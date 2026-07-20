#!/usr/bin/env python3
"""盲测 Step3: 汇总LLM提取结果 + A10修正比对引擎裁决
用法: python scripts/blind_test_compare.py --extracted-dir /tmp/ --batch-pattern 'blind_batch_*_extracted.json' --engine-data /tmp/blind_test_batch.json [--verdict-csv data/verdict_v7.csv]
产出: 控制台统计 + /tmp/blind_test_summary.json
A10修正: 看多=持股/试探/加仓/持有, 非看多=空仓/减仓/观望/无. 仅跨边界计矛盾.
"""
import json, glob, re, argparse
from collections import Counter

def to_direction_engine(v):
    v = str(v).strip()
    if v in ('持股', '试探', '持股(警戒)'): return '看多'
    return '非看多'

def to_direction_llm(op):
    op = str(op).strip()
    if op in ('加仓', '持有', '持股'): return '看多'
    return '非看多'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--extracted-dir', default='/tmp/')
    parser.add_argument('--batch-pattern', default='blind_batch_*_extracted.json')
    parser.add_argument('--engine-data', default='/tmp/blind_test_batch.json')
    parser.add_argument('--verdict-csv', default=None)  # optional: reload engine from latest CSV
    args = parser.parse_args()

    # Load LLM extractions
    all_llm = {}
    for fpath in sorted(glob.glob(args.extracted_dir + args.batch_pattern)):
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data if isinstance(data, list) else list(data.values())
        for item in items:
            ad = item.get('analysis_date', '')
            if ad: all_llm[ad] = item

    # Load engine data (from batch JSON or fresh CSV)
    engine = {}
    if args.verdict_csv:
        import csv
        with open(args.verdict_csv, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                v = row.get('verdict_main', '')
                engine[row['date']] = {
                    'verdict_main': v,
                    'direction': to_direction_engine(v),
                    'regime_sh': row.get('regime_sh', ''),
                    'osc_origin_sh': row.get('osc_origin_sh', ''),
                }
    elif args.engine_data:
        with open(args.engine_data, 'r', encoding='utf-8') as f:
            batch_data = json.load(f)
        for d in batch_data:
            v = d.get('verdict_main', '')
            engine[d['analysis_date']] = {
                'verdict_main': v,
                'direction': to_direction_engine(v),
            }

    # Compare
    by_year = {}
    for ad, item in sorted(all_llm.items()):
        eng = engine.get(ad)
        if not eng: continue
        year = int(ad[:4])
        llm_dir = to_direction_llm(item.get('operation', ''))
        match = (llm_dir == eng['direction'])
        
        if year not in by_year:
            by_year[year] = {'total': 0, 'match': 0, 'mismatches': []}
        by_year[year]['total'] += 1
        if match:
            by_year[year]['match'] += 1
        else:
            by_year[year]['mismatches'].append({
                'date': ad,
                'engine_verdict': eng['verdict_main'],
                'engine_dir': eng['direction'],
                'llm_operation': item.get('operation', ''),
                'llm_dir': llm_dir,
                'llm_core': item.get('core_judgment', ''),
            })

    # Print
    all_total = sum(y['total'] for y in by_year.values())
    all_match = sum(y['match'] for y in by_year.values())
    print(f"{'='*55}")
    print(f"  一致性盲测 v17 · A10修正 · {all_match}/{all_total} = {all_match/all_total*100:.1f}%")
    print(f"{'='*55}")
    
    for year in sorted(by_year.keys()):
        y = by_year[year]
        pct = y['match']/y['total']*100
        flag = ' ⚠️' if pct < 65 else ''
        print(f"  {year}: {y['match']}/{y['total']} = {pct:.0f}%{flag}")
        for m in y['mismatches']:
            print(f"    {m['date']} ✗ 引擎={m['engine_verdict']}({m['engine_dir']}) 徐小明={m['llm_operation']}({m['llm_dir']})  → {m['llm_core']}")

    # Mismatch analysis
    all_mismatches = [m for y in by_year.values() for m in y['mismatches']]
    mc = Counter()
    for m in all_mismatches:
        mc[f"引擎{m['engine_dir']} vs 徐小明{m['llm_dir']}"] += 1
    print(f"\n  方向矛盾: {len(all_mismatches)}篇")
    for k, v in mc.most_common():
        print(f"    {k}: {v}篇")

if __name__ == '__main__':
    main()
