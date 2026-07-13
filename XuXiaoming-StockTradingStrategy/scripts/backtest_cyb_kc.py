#!/usr/bin/env python3
"""
创业板+科创50 双共振回测
========================
验证双创共振是否对科技分化行情有预测价值。

核心问题：
1. 共振_偏多/偏空状态下，双创指数后续表现是否显著区别于主板？
2. 双创共振是否比六指数共振更早/更准地捕捉到科技股方向？
"""
import pandas as pd
from collections import defaultdict

df = pd.read_csv('data/verdict_v7.csv')
df['date'] = pd.to_datetime(df['date'])
df = df[df['date'] >= '2020-01-01'].copy()  # 科创50起始

print("=" * 60)
print("1. 双创共振状态分布")
print("=" * 60)
for state in ['共振_偏多', '共振_偏空', '分化', '混合']:
    cnt = (df['cyb_kc_resonance'] == state).sum()
    print(f"  {state}: {cnt}天 ({cnt/len(df)*100:.1f}%)")

print("\n" + "=" * 60)
print("2. 各共振状态下 5/10/20 日指数收益")
print("=" * 60)

def forward_return(series, days):
    """前向收益"""
    return series.shift(-days) / series - 1

for state in ['共振_偏多', '共振_偏空', '混合']:
    subset = df[df['cyb_kc_resonance'] == state].copy()
    if len(subset) < 10: continue
    
    print(f"\n--- {state} ({len(subset)}天) ---")
    
    for horizon in [5, 10, 20]:
        ret_cyb = forward_return(df['close_cyb'], horizon)
        ret_kc = forward_return(df['close_kc'], horizon)
        ret_sh = forward_return(df['close_sh'], horizon)
        ret_sz = forward_return(df['close_sz'], horizon)
        
        # Only days where this state was active
        mask = df['cyb_kc_resonance'] == state
        valid_cyb = mask & ret_cyb.notna()
        valid_kc = mask & ret_kc.notna()
        valid_sh = mask & ret_sh.notna()
        valid_sz = mask & ret_sz.notna()
        
        m_cyb = ret_cyb[valid_cyb].mean() * 100
        m_kc = ret_kc[valid_kc].mean() * 100
        m_sh = ret_sh[valid_sh].mean() * 100
        m_sz = ret_sz[valid_sz].mean() * 100
        
        spread_cyb_vs_sh = m_cyb - m_sh
        spread_kc_vs_sh = m_kc - m_sh
        
        print(f"  {horizon:2d}日: CYB={m_cyb:+.2f}% KC={m_kc:+.2f}% SH={m_sh:+.2f}% SZ={m_sz:+.2f}% | 超额: CYBvsSH={spread_cyb_vs_sh:+.2f}% KCvsSH={spread_kc_vs_sh:+.2f}%")

print("\n" + "=" * 60)
print("3. 双创共振 vs 六指数共振 — 领先/滞后分析")
print("=" * 60)

# 共振切换点对比
df['prev_ck'] = df['cyb_kc_resonance'].shift(1)
df['prev_six'] = df['resonance'].shift(1)

ck_changes = df[df['cyb_kc_resonance'] != df['prev_ck']]
six_changes = df[df['resonance'] != df['prev_six']]

print(f"  双创共振切换次数: {len(ck_changes)}")
print(f"  六指数共振切换次数: {len(six_changes)}")

# 双创先于六指数转多的情况
ck_turns_bull = df[(df['prev_ck'] != '共振_偏多') & (df['cyb_kc_resonance'] == '共振_偏多')]
ck_turns_bear = df[(df['prev_ck'] != '共振_偏空') & (df['cyb_kc_resonance'] == '共振_偏空')]

print(f"\n  双创转'共振_偏多': {len(ck_turns_bull)}次")
print(f"  双创转'共振_偏空': {len(ck_turns_bear)}次")

# 双创转多时，六指数是什么状态
print("\n  双创转偏多时，六指数状态:")
for res_state in df['resonance'].unique():
    cnt = len(ck_turns_bull[ck_turns_bull['resonance'] == res_state])
    if cnt > 0:
        print(f"    六指数={res_state}: {cnt}次")

print("\n" + "=" * 60)
print("4. 双创共振失效分析 — 共振_偏多但后续下跌的案例")
print("=" * 60)

# 共振_偏多但20日后双创跑输上证
mask_bull = df['cyb_kc_resonance'] == '共振_偏多'
ret_cyb_20 = forward_return(df['close_cyb'], 20)
ret_sh_20 = forward_return(df['close_sh'], 20)

failures = df[mask_bull & ret_cyb_20.notna() & ret_sh_20.notna()].copy()
failures['cyb_excess'] = ret_cyb_20[failures.index] - ret_sh_20[failures.index]
failures = failures[failures['cyb_excess'] < -0.03]  # 跑输3%以上

print(f"  共振_偏多后20日双创跑输上证>3%: {len(failures)}次")
if len(failures) > 0:
    print(f"  案例:")
    for _, r in failures.head(10).iterrows():
        print(f"    {r['date'].strftime('%Y-%m-%d')} CYB超额={r['cyb_excess']*100:.1f}% 六指数共振={r['resonance']}")

print("\n" + "=" * 60)
print("5. 结论速览")
print("=" * 60)

# Overall stats
bull_mask = df['cyb_kc_resonance'] == '共振_偏多'
bear_mask = df['cyb_kc_resonance'] == '共振_偏空'
mixed_mask = df['cyb_kc_resonance'] == '混合'

ret_cyb_20_all = forward_return(df['close_cyb'], 20)
ret_sh_20_all = forward_return(df['close_sh'], 20)

for label, mask in [('共振_偏多', bull_mask), ('共振_偏空', bear_mask), ('混合', mixed_mask)]:
    valid = mask & ret_cyb_20_all.notna()
    cyb_avg = ret_cyb_20_all[valid].mean() * 100
    sh_avg = ret_sh_20_all[valid].mean() * 100
    win_rate = (ret_cyb_20_all[valid] > 0).mean() * 100
    print(f"  {label}: CYB 20日均收益={cyb_avg:+.2f}% SH={sh_avg:+.2f}% CYB胜率={win_rate:.0f}%")
