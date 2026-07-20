#!/usr/bin/env python3
"""盲测 Step1: 按年随机抽样 + 匹配本地文章 + 提取引擎裁决

用法:
  python scripts/blind_sample.py [--year N] [--n-per-year 60] [--seed 42]

产出 /tmp/blind_test_batch.json (全量) + /tmp/blind_batch_{year}.json (按年)
"""
import os, re, json, random, argparse
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument('--verdict', default='data/verdict_v7.csv')
parser.add_argument('--articles', default='/home/admin/file-transfer/徐小明/徐小明文集/')
parser.add_argument('--n-per-year', type=int, default=60)
parser.add_argument('--seed', type=int, default=42)
parser.add_argument('--year', type=int, default=0)
parser.add_argument('--output', default='/tmp/blind_test_batch.json')
args = parser.parse_args()

verdict = pd.read_csv(args.verdict)
verdict['date'] = pd.to_datetime(verdict['date'])
verdict = verdict.sort_values('date')
all_dates = verdict['date'].dt.date.tolist()

article_dir = args.articles
article_files = os.listdir(article_dir)
publish_map = {}
for f in article_files:
    if not f.endswith('.md'): continue
    m = re.match(r'(\d{8})_', f)
    if m: publish_map[m.group(1)] = f

def find_article(d):
    wd = d.weekday()
    if wd == 6: return None, None
    pub = d - timedelta(days=3) if wd == 0 else d - timedelta(days=1)
    pub_str = pub.strftime('%Y%m%d')
    if pub_str in publish_map: return publish_map[pub_str], pub_str
    return None, None

random.seed(args.seed)
results = []
missing = []
year_range = [args.year] if args.year > 0 else range(2020, 2027)

for year in year_range:
    year_dates = [d for d in all_dates if d.year == year and d.weekday() != 6]
    n = min(args.n_per_year, len(year_dates))
    sampled = sorted(random.sample(year_dates, n))
    for d in sampled:
        fname, pub = find_article(d)
        if fname:
            fpath = os.path.join(article_dir, fname)
            with open(fpath, 'r', encoding='utf-8') as fh:
                content = fh.read()
            row = verdict[verdict['date'] == pd.Timestamp(d)]
            if len(row) > 0:
                r = row.iloc[0]
                results.append({
                    'analysis_date': str(d), 'publish_date': pub,
                    'filename': fname, 'content': content,
                    'verdict_main': str(r.get('verdict_main', '')),
                    'verdict_tech': str(r.get('verdict_tech', '')),
                    'regime_sh': str(r.get('regime_sh', '')),
                    'year': year, 'weekday': d.strftime('%A'),
                })
            else:
                missing.append((str(d), 'no_verdict'))
        else:
            missing.append((str(d), 'no_article'))

print(f"Sampled: {args.n_per_year}/year x {len(year_range)}y = {args.n_per_year*len(year_range)}")
print(f"Matched: {len(results)}  Missing: {len(missing)}")
for year in year_range:
    yr_count = sum(1 for r in results if r['year'] == year)
    print(f"  {year}: {yr_count}/{args.n_per_year}")

with open(args.output, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"Saved {len(results)} to {args.output}")

for year in year_range:
    yr_items = [r for r in results if r['year'] == year]
    if yr_items:
        yr_file = f"/tmp/blind_batch_{year}.json"
        with open(yr_file, 'w', encoding='utf-8') as f:
            json.dump(yr_items, f, ensure_ascii=False, indent=2)
