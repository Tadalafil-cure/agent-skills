#!/usr/bin/env python3
"""盲测 Step2: 将 batch JSON 拆分为子 Agent 处理批次 (每批20篇)

用法:
  python scripts/blind_split.py [--batch-size 20] [--input /tmp/blind_test_batch.json]
"""
import json, argparse

parser = argparse.ArgumentParser()
parser.add_argument('--input', default='/tmp/blind_test_batch.json')
parser.add_argument('--batch-size', type=int, default=20)
args = parser.parse_args()

with open(args.input, 'r', encoding='utf-8') as f:
    articles = json.load(f)

batch_size = args.batch_size
batches = []
for i in range(0, len(articles), batch_size):
    batches.append(articles[i:i+batch_size])

# 每批拆成 full (含全文) 和 summary (仅元数据+短文预览)
for idx, batch in enumerate(batches):
    trimmed = []
    for a in batch:
        trimmed.append({
            'analysis_date': a['analysis_date'],
            'filename': a['filename'],
            'verdict_main': a['verdict_main'],
            'verdict_tech': a['verdict_tech'],
            'year': a['year'],
            'weekday': a['weekday'],
            'content_preview': a['content'][:150] + '...',
        })
    with open(f'/tmp/blind_batch_{idx:02d}_full.json', 'w', encoding='utf-8') as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)
    with open(f'/tmp/blind_batch_{idx:02d}_summary.json', 'w', encoding='utf-8') as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)

print(f"Split {len(articles)} into {len(batches)} batches of {batch_size}")
for idx, batch in enumerate(batches):
    print(f"  Batch {idx:02d}: {len(batch)} articles (years {batch[0]['year']}-{batch[-1]['year']})")
