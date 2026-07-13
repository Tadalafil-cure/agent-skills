"""
月周低9 区分度回测
================
问题：月低9/周低9 窗口对主板和科技是否应该区分？

当前：所有指数共享同一个 month_win/week_win（基于深证成指序列）。
假设：科创50/创业板的月周低9窗口效应可能与主板不同。
"""
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import csv

BASE = '/home/admin/.hermes/skills/XuXiaoming-StockTradingStrategy'

def load_seq(path, index_name):
    seq = defaultdict(dict)
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['index_name'] == index_name:
                seq[row['date']][row['period']] = row['seq_type']
    return seq

seq_path = f'{BASE}/data/turn_sequence_events.csv'

# 四指数各自加载序列
seqs = {}
for name in ['深证成指', '上证指数', '创业板指', '科创50']:
    seqs[name] = load_seq(seq_path, name)

df = pd.read_csv(f'{BASE}/data/verdict_v7.csv')
df['date'] = pd.to_datetime(df['date'])
df = df[df['date'] >= '2020-01-01'].copy()

# 为每个指数独立计算月周低9窗口
for idx_name in ['深证成指', '上证指数', '创业板指', '科创50']:
    seq = seqs[idx_name]
    col_month = f'month_win_{idx_name}'
    col_week = f'week_win_{idx_name}'
    df[col_month] = False
    df[col_week] = False
    
    for i, row in df.iterrows():
        d = row['date']
        dt = datetime.strptime(str(d)[:10], '%Y-%m-%d')
        
        for j in range(60):
            cd = (dt - timedelta(days=j)).strftime('%Y-%m-%d')
            if cd in seq and '月线' in seq[cd]:
                if j <= 40:
                    df.at[i, col_month] = True
                break
        
        for j in range(30):
            cd = (dt - timedelta(days=j)).strftime('%Y-%m-%d')
            if cd in seq and '周线' in seq[cd]:
                if j <= 20:
                    df.at[i, col_week] = True
                break

print("=" * 60)
print("1. 各指数月低9窗口天数（2020至今）")
print("=" * 60)
for name in ['深证成指', '上证指数', '创业板指', '科创50']:
    col = f'month_win_{name}'
    cnt = df[col].sum()
    print(f"  {name}: {cnt}天 ({cnt/len(df)*100:.0f}%)")

print("\n" + "=" * 60)
print("2. 月低9窗口内 20日收益对比")
print("=" * 60)

close_map = {'深证成指': 'close_sz', '上证指数': 'close_sh', '创业板指': 'close_cyb', '科创50': 'close_kc'}

for target_name in ['深证成指', '上证指数', '创业板指', '科创50']:
    col_month = f'month_win_{target_name}'
    mask = df[col_month] == True
    close_col = close_map[target_name]
    
    ret20 = df[close_col].shift(-20) / df[close_col] - 1
    valid = mask & ret20.notna()
    
    if valid.sum() < 5:
        continue
    
    avg_ret = ret20[valid].mean() * 100
    win_rate = (ret20[valid] > 0).mean() * 100
    print(f"  {target_name}月低9窗口 ({valid.sum()}天): 均收益={avg_ret:+.2f}% 胜率={win_rate:.0f}%")

    # Compare: same window for SZ vs using SZ's window for other indices
    if target_name != '深证成指':
        sz_col = f'month_win_深证成指'
        mask_sz = df[sz_col] == True
        ret20_other = df[close_col].shift(-20) / df[close_col] - 1
        valid_sz = mask_sz & ret20_other.notna()
        avg_sz = ret20_other[valid_sz].mean() * 100
        print(f"    (如果用深证月低9窗口: 均收益={avg_sz:+.2f}%)")

print("\n" + "=" * 60)
print("3. 月低9窗口对四指数的覆盖是否重叠？")
print("=" * 60)

# Overlap: do all indices have month_win at the same time?
all_four = (df['month_win_深证成指'].astype(int) + 
            df['month_win_上证指数'].astype(int) + 
            df['month_win_创业板指'].astype(int) + 
            df['month_win_科创50'].astype(int))

print(f"  四指数同时月低9: {(all_four == 4).sum()}天")
print(f"  至少三个: {(all_four >= 3).sum()}天")
print(f"  仅深证: {(df['month_win_深证成指'] and not df['month_win_创业板指']).sum()}天")  # 简化

# Check divergence: SZ in window but CYB not
sz_only = df[df['month_win_深证成指'] & ~df['month_win_创业板指']]
cyb_only = df[~df['month_win_深证成指'] & df['month_win_创业板指']]
print(f"  仅深证在窗口: {len(sz_only)}天")
print(f"  仅创业板在窗口: {len(cyb_only)}天")

print("\n" + "=" * 60)
print("4. 周低9窗口 对比")
print("=" * 60)
for target_name in ['深证成指', '上证指数', '创业板指', '科创50']:
    col_week = f'week_win_{target_name}'
    mask = df[col_week] == True
    close_col = close_map[target_name]
    
    ret20 = df[close_col].shift(-20) / df[close_col] - 1
    valid = mask & ret20.notna()
    
    if valid.sum() < 5:
        continue
    
    avg_ret = ret20[valid].mean() * 100
    win_rate = (ret20[valid] > 0).mean() * 100
    print(f"  {target_name}周低9窗口 ({valid.sum()}天): 均收益={avg_ret:+.2f}% 胜率={win_rate:.0f}%")

print("\n" + "=" * 60)
print("5. 结论")
print("=" * 60)
# Compare SZ month_win vs CYB month_win for CYB performance
sz_mask = df['month_win_深证成指'] == True
cyb_mask = df['month_win_创业板指'] == True
ret_cyb = df['close_cyb'].shift(-20) / df['close_cyb'] - 1

sz_valid = sz_mask & ret_cyb.notna()
cyb_valid = cyb_mask & ret_cyb.notna()

if sz_valid.sum() > 0 and cyb_valid.sum() > 0:
    sz_avg = ret_cyb[sz_valid].mean() * 100
    cyb_avg = ret_cyb[cyb_valid].mean() * 100
    print(f"  创业板在深证月低9窗口: {sz_avg:+.2f}%")
    print(f"  创业板在自己月低9窗口: {cyb_avg:+.2f}%")
    print(f"  差异: {cyb_avg - sz_avg:+.2f}%")
    
    if abs(cyb_avg - sz_avg) < 1:
        print(f"\n  → 差异微小，不需要区分。统一使用深证月低9窗口即可。")
    elif cyb_avg > sz_avg:
        print(f"\n  → 创业板自己窗口更好，建议区分。")
    else:
        print(f"\n  → 深证窗口更好，不需要区分。")
