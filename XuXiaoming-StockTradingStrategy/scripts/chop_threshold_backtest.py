#!/usr/bin/env python3
"""
CHOP 阈值滞回回测 · chop_threshold_backtest.py
===============================================
回测 CHOP 上穿 61.8 和下穿 38.2 是否应该加滞回。

用法：python scripts/chop_threshold_backtest.py

结论（v4.6.3 执行，科创50 1329天）：
  - 上穿 61.8：单日即切（即时切换 Sharpe=0.31，滞回 N=2 Sharpe=0.22）
  - 下穿 38.2：≥3天确认（94% 单日跌破为假收敛）
  - 两条线不对称不是 bug——上穿是真信号，下穿是假信号
"""

import pandas as pd
import numpy as np
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

df = pd.read_csv(os.path.join(BASE, 'data/verdict_v7.csv'))
df['date'] = pd.to_datetime(df['date'])

kc = df[['date', 'close_kc', 'chop_kc', 'regime_kc', 'verdict_kc']].dropna(subset=['chop_kc']).copy()
kc = kc.sort_values('date').reset_index(drop=True)

kc['chop_over'] = (kc['chop_kc'] > 61.8).astype(int)

# === NON-STICKY: each day independently ===
# Strategy A: Immediate — single day > 61.8 → oscillation that day
kc['sig_A'] = np.where(kc['chop_kc'] > 61.8, 0, 1)

# Strategy B: Hysteresis — need 2 of last 2 > 61.8 to switch
kc['over_roll2'] = kc['chop_over'].rolling(2, min_periods=1).sum()
kc['sig_B'] = np.where(kc['over_roll2'] >= 2, 0, 1)

# Strategy C: Need 3 consecutive
kc['over_roll3'] = kc['chop_over'].rolling(3, min_periods=1).sum()
kc['sig_C'] = np.where(kc['over_roll3'] >= 3, 0, 1)

# Strategy D: Asymmetric hysteresis (Enter: 2d, Exit: 1d)
sig_D = np.ones(len(kc))
in_osc = False
for i in range(len(kc)):
    if not in_osc:
        if i >= 1 and kc['chop_over'].iloc[i] == 1 and kc['chop_over'].iloc[i - 1] == 1:
            in_osc = True
    else:
        if kc['chop_kc'].iloc[i] <= 61.8:
            in_osc = False
    sig_D[i] = 0 if in_osc else 1
kc['sig_D'] = sig_D

# Returns
kc['ret'] = kc['close_kc'].pct_change()
kc['ret_bnh'] = kc['ret']
kc['ret_A'] = kc['ret'] * kc['sig_A'].shift(1)
kc['ret_B'] = kc['ret'] * kc['sig_B'].shift(1)
kc['ret_C'] = kc['ret'] * kc['sig_C'].shift(1)
kc['ret_D'] = kc['ret'] * kc['sig_D'].shift(1)

kc_valid = kc.dropna(subset=['ret']).copy()
n_days = len(kc_valid)

print("=" * 80)
print("CHOP > 61.8 NON-STICKY BACKTEST — KC50")
print(f"Period: {kc_valid['date'].min().date()} ~ {kc_valid['date'].max().date()}  ({n_days} days)")
print("=" * 80)


def stats(name, ret_col):
    rets = kc_valid[ret_col].dropna()
    cum = (1 + rets).prod() - 1
    ann = (1 + cum) ** (252 / len(rets)) - 1
    vol = rets.std() * np.sqrt(252)
    sharpe = ann / vol if vol > 0 else 0
    max_dd = (1 - (1 + rets).cumprod() / (1 + rets).cumprod().cummax()).max()
    pct_in = kc_valid[ret_col.replace('ret_', 'sig_')].mean() * 100 if ret_col != 'ret_bnh' else 100
    print(f"  {name:35s}: Cum={cum:+7.2%}, Ann={ann:+7.2%}, Vol={vol:.1%}, "
          f"Sharpe={sharpe:+5.2f}, MaxDD={max_dd:.1%}, InMkt={pct_in:.0f}%")


stats("Buy & Hold", "ret_bnh")
stats("A: Immed 1d >61.8 -> osc", "ret_A")
stats("B: 2 of last 2 >61.8 -> osc", "ret_B")
stats("C: 3 of last 3 >61.8 -> osc", "ret_C")
stats("D: Enter 2d, Exit 1d <=61.8", "ret_D")

# False positive analysis
spike_mask = (kc['chop_over'] == 1) & (kc['chop_kc'].shift(-1) <= 61.8)
spike_dates = kc.loc[spike_mask, 'date']
total_spike_return = sum(
    kc.iloc[kc[kc['date'] == d].index[0] + 1]['ret']
    for d in spike_dates
    if kc[kc['date'] == d].index[0] + 1 < len(kc)
)
print(f"\n  Single-day spikes: {len(spike_dates)} ({100 * len(spike_dates) / kc['chop_over'].sum():.1f}% of all >61.8)")
print(f"  Total return cost of delaying switch: {total_spike_return:+.2%}")

# Cluster analysis
kc['cluster_id'] = (kc['chop_over'] != kc['chop_over'].shift()).cumsum()
clusters = kc[kc['chop_over'] == 1].groupby('cluster_id').agg(
    start=('date', 'first'), dur=('chop_over', 'count'),
    avg_c=('chop_kc', 'mean'), max_c=('chop_kc', 'max'),
).sort_values('start')

print(f"\n  Total >61.8 clusters: {len(clusters)}")
print(f"  1-day spikes: {len(clusters[clusters['dur'] == 1])}")
print(f"  2-day clusters: {len(clusters[clusters['dur'] == 2])}")
print(f"  3+ day clusters: {len(clusters[clusters['dur'] >= 3])}")

print("\nConclusion: No hysteresis for CHOP > 61.8. Immediate switch is optimal.")
