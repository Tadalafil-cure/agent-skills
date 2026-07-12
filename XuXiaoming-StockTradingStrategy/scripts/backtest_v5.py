#!/usr/bin/env python3
"""全量回测 + 前向收益"""
import csv
from datetime import datetime, timedelta
from collections import defaultdict
import os
from pathlib import Path

BASE = str(Path(__file__).resolve().parent.parent)


def main(verdict_file: str = None):
    if verdict_file is None:
        verdict_file = os.path.join(BASE, 'data/verdict_v7.csv')

    # Load verdict
    verdicts = []
    with open(verdict_file, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            row['close'] = float(row['close'])
            verdicts.append(row)

    n = len(verdicts)

    # Forward returns
    for i in range(n):
        d_str = verdicts[i]['date']
        d = datetime.strptime(d_str, '%Y-%m-%d')
        c = verdicts[i]['close']

        # 5d forward
        fwd5 = None
        for j in range(i+1, min(i+8, n)):
            if (datetime.strptime(verdicts[j]['date'], '%Y-%m-%d') - d).days >= 4:
                fwd5 = verdicts[j]['close']
                break
        if fwd5:
            verdicts[i]['fwd_5d'] = (fwd5 / c - 1) * 100

        # 20d forward
        fwd20 = None
        target = d + timedelta(days=28)
        for j in range(i+1, min(i+22, n)):
            fj = datetime.strptime(verdicts[j]['date'], '%Y-%m-%d')
            if fj >= target:
                fwd20 = verdicts[j]['close']
                break
        if not fwd20 and i+1 < n:
            fwd20 = verdicts[min(i+20, n-1)]['close']
        if fwd20:
            verdicts[i]['fwd_20d'] = (fwd20 / c - 1) * 100

    # By verdict type
    print('=' * 70)
    print('裁决引擎 v7  全量回测')
    print('=' * 70)
    print(f'总交易日: {n}')
    print()

    # Signal stats
    by_verdict = defaultdict(list)
    for v in verdicts:
        cat = v['verdict']
        if '持股' in cat: cat = '持股类'
        elif '试探' in cat: cat = '试探类'
        by_verdict[cat].append(v)

    print(f'{"信号":>12} {"天数":>6} {"占比":>6} {"5d收益":>8} {"5d胜率":>7} {"20d收益":>8} {"20d胜率":>7}')
    print('-' * 65)
    for cat in ['持股类', '试探类', '空仓', '观望']:
        items = by_verdict[cat]
        cnt = len(items)
        pct = cnt / n * 100

        f5 = [x['fwd_5d'] for x in items if 'fwd_5d' in x]
        f20 = [x['fwd_20d'] for x in items if 'fwd_20d' in x]

        r5 = f'{sum(f5)/len(f5):+.2f}%' if f5 else 'N/A'
        w5 = f'{sum(1 for x in f5 if x>0)/len(f5)*100:.0f}%' if f5 else 'N/A'
        r20 = f'{sum(f20)/len(f20):+.2f}%' if f20 else 'N/A'
        w20 = f'{sum(1 for x in f20 if x>0)/len(f20)*100:.0f}%' if f20 else 'N/A'

        print(f'{cat:>12} {cnt:>6} {pct:>5.0f}% {r5:>8} {w5:>7} {r20:>8} {w20:>7}')

    # Sub-breakdown for 试探
    print()
    print('试探类子分类:')
    tan_by_type = defaultdict(list)
    for v in verdicts:
        if '试探' in v['verdict']:
            tan_by_type[v['verdict']].append(v)
    for k, items in sorted(tan_by_type.items()):
        f20 = [x['fwd_20d'] for x in items if 'fwd_20d' in x]
        if f20:
            r20 = sum(f20)/len(f20)
            w20 = sum(1 for x in f20 if x>0)/len(f20)*100
            print(f'  {k}: {len(items)}天 20d={r20:+.2f}% 胜率={w20:.0f}%')

    # Annual breakdown
    print()
    print('年度分解:')
    years = defaultdict(lambda: defaultdict(list))
    for v in verdicts:
        yr = v['date'][:4]
        cat = v['verdict']
        if '持股' in cat: cat = '持股类'
        elif '试探' in cat: cat = '试探类'
        years[yr][cat].append(v)

    print(f'{"年":>6} {"持股":>6} {"试探":>6} {"空仓":>6} {"观望":>6} {"持股20d":>9} {"试探20d":>9}')
    print('-' * 55)
    for yr in sorted(years.keys()):
        y = years[yr]
        hold = len(y.get('持股类', [])); tanshi = len(y.get('试探类', []))
        short = len(y.get('空仓', [])); watch = len(y.get('观望', []))
        h20 = sum(x.get('fwd_20d', 0) or 0 for x in y.get('持股类', []))
        h20 = f'{h20/len(y["持股类"]):+.2f}%' if y.get('持股类') else 'N/A'
        t20 = sum(x.get('fwd_20d', 0) or 0 for x in y.get('试探类', []))
        t20 = f'{t20/len(y["试探类"]):+.2f}%' if y.get('试探类') else 'N/A'
        print(f'{yr:>6} {hold:>6} {tanshi:>6} {short:>6} {watch:>6} {h20:>9} {t20:>9}')

    # Key dates
    print()
    print('关键节点:')
    targets = {
        '2020-03-19': '疫情底',
        '2021-02-18': '3731顶',
        '2022-04-27': '徐抄底',
        '2024-02-05': '2635底',
        '2024-09-19': '924前',
        '2024-09-24': '924突破',
        '2024-10-08': '3674顶',
        '2025-04-07': '贸易战',
    }
    for v in verdicts:
        if v['date'] in targets:
            f20 = f'{v.get("fwd_20d",0):+.1f}%' if 'fwd_20d' in v else 'N/A'
            print(f'  {v["date"]} {targets[v["date"]]:8s} → {v["verdict"]:20s} 20d={f20}')


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
