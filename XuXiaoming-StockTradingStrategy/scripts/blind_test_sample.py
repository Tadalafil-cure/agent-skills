#!/usr/bin/env python3
"""盲测 Step1: 抽样 60天/年 + 匹配本地文章 + 提取引擎裁决
用法: python scripts/blind_test_sample.py [--seed 42] [--per-year 60] [--years 2020-2026]
产出: /tmp/blind_test_batch.json 按年分批JSON
依赖: verdict_v7.csv, /home/admin/file-transfer/徐小明/徐小明文集/
"""
import os, re, json, random, argparse
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--per-year', type=int, default=60)
    parser.add_argument('--output', default='/tmp/blind_test_batch.json')
    parser.add_argument('--article-dir', default='/home/admin/file-transfer/徐小明/徐小明文集/')
    args = parser.parse_args()
    random.seed(args.seed)

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    verdict = pd.read_csv(os.path.join(BASE, 'data/verdict_v7.csv'))
    verdict['date'] = pd.to_datetime(verdict['date']).dt.date

    # Index articles
    article_files = os.listdir(args.article_dir)
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

    results = []
    years = sorted(set(d.year for d in verdict['date']))
    
    for year in years:
        year_dates = [d for d in sorted(verdict['date'].unique()) if d.year == year and d.weekday() != 6]
        n = min(args.per_year, len(year_dates))
        sampled = sorted(random.sample(year_dates, n))
        
        for d in sampled:
            fname, pub = find_article(d)
            if not fname: continue
            fpath = os.path.join(args.article_dir, fname)
            with open(fpath, 'r', encoding='utf-8') as fh:
                content = fh.read()
            row = verdict[verdict['date'] == d]
            if len(row) == 0: continue
            r = row.iloc[0]
            results.append({
                'analysis_date': str(d), 'publish_date': pub, 'filename': fname,
                'content': content, 'year': year, 'weekday': d.strftime('%A'),
                'verdict_main': str(r.get('verdict_main', '')),
                'regime_sh': str(r.get('regime_sh', '')),
            })

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Sampled {len(results)} articles → {args.output}")

if __name__ == '__main__':
    main()
