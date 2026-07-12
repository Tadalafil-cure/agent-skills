#!/usr/bin/env python3
"""
徐小明裁决引擎 v1.0
L1 月周九转 → L2 三合一市况 → L3 结构修边 → L4 分钟线(预留)

输入：
  data/daily_ma_channels.csv     — 深证成指 OHLC
  data/structure_signals.csv     — MACD 结构信号
  data/turn_sequence_events.csv  — 月/周九转序列

输出：
  data/verdict_daily.csv         — 每日裁决
"""
import csv, math, sys
from datetime import datetime, timedelta
from collections import defaultdict


def load_ohlc(path):
    """加载深证成指日线"""
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['index_name'] == '深证成指':
                c = float(row['close'])
                if c > 0:
                    rows.append({
                        'date': row['date'],
                        'close': c,
                        'high': float(row['high']),
                        'low': float(row['low'])
                    })
    return rows


def compute_regime_classifier(rows, lookback=250):
    """
    三合一市况分类器
    ER30 + ADX14 + 标准化动量(20日)
    250天滚动65%分位投票，无滞回
    """
    n = len(rows)

    # --- ER(30) ---
    er30 = [0.0] * n
    for i in range(30, n):
        net = abs(rows[i]['close'] - rows[i - 30]['close'])
        path = sum(abs(rows[j]['close'] - rows[j - 1]['close'])
                   for j in range(i - 29, i + 1))
        er30[i] = net / path if path > 0 else 0

    # --- ADX(14) ---
    period = 14
    tr = [0.0] * n
    pd = [0.0] * n
    md = [0.0] * n
    for i in range(1, n):
        h, l = rows[i]['high'], rows[i]['low']
        ph, pl, pc = rows[i - 1]['high'], rows[i - 1]['low'], rows[i - 1]['close']
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
        up = h - ph
        dn = pl - l
        pd[i] = up if up > dn and up > 0 else 0
        md[i] = dn if dn > up and dn > 0 else 0

    def wilder(d, p):
        o = [0.0] * n
        for i in range(p, n):
            if i == p:
                o[i] = sum(d[1:p + 1])
            else:
                o[i] = o[i - 1] - o[i - 1] / p + d[i]
        return o

    atr_w = wilder(tr, period)
    pdi_w = wilder(pd, period)
    mdi_w = wilder(md, period)
    adx_w = [0.0] * n
    av = 0.0
    for i in range(period * 2, n):
        pv = 100 * pdi_w[i] / atr_w[i] if atr_w[i] > 0 else 0
        mv = 100 * mdi_w[i] / atr_w[i] if atr_w[i] > 0 else 0
        dx = abs(pv - mv) / (pv + mv) * 100 if (pv + mv) > 0 else 0
        if av == 0:
            total = 0.0
            cnt = 0
            for j in range(i - period + 1, i + 1):
                if j < period:
                    continue
                pj = 100 * pdi_w[j] / atr_w[j] if atr_w[j] > 0 else 0
                mj = 100 * mdi_w[j] / atr_w[j] if atr_w[j] > 0 else 0
                dxj = abs(pj - mj) / (pj + mj) * 100 if (pj + mj) > 0 else 0
                total += dxj
                cnt += 1
            av = total / cnt if cnt > 0 else 0
        else:
            av = (av * (period - 1) + dx) / period
        adx_w[i] = av

    # --- 标准化动量(20日) ---
    mom = [0.0] * n
    for i in range(20, n):
        ret = math.log(rows[i]['close'] / rows[i - 20]['close'])
        returns = [math.log(rows[j]['close'] / rows[j - 1]['close'])
                   for j in range(i - 19, i + 1)]
        std = (sum(r * r for r in returns) / 20) ** 0.5
        mom[i] = ret / (std * math.sqrt(20)) if std > 0 else 0

    # --- 投票 ---
    result = [None] * n
    for i in range(lookback, n):
        ew = [er30[j] for j in range(i - lookback, i + 1) if er30[j] > 0]
        aw = [adx_w[j] for j in range(i - lookback, i + 1) if adx_w[j] > 0]
        mw = [abs(mom[j]) for j in range(i - lookback, i + 1) if mom[j] != 0]
        if len(ew) < 100:
            continue
        ew.sort()
        aw.sort()
        mw.sort()
        eth = ew[int(len(ew) * 0.65)]
        ath = aw[int(len(aw) * 0.65)]
        mth = mw[int(len(mw) * 0.65)]

        er = er30[i]
        adx = adx_w[i]
        mv = mom[i]
        p = 100 * pdi_w[i] / atr_w[i] if atr_w[i] > 0 else 0
        m = 100 * mdi_w[i] / atr_w[i] if atr_w[i] > 0 else 0

        ve = 1 if er >= eth else 0
        va = 1 if adx >= ath else 0
        vm = 1 if abs(mv) >= mth else 0
        votes = ve + va + vm

        dv = 0
        if er >= ew[int(len(ew) * 0.50)]:
            dv += 1 if rows[i]['close'] > rows[i - 30]['close'] else -1
        if adx >= aw[int(len(aw) * 0.50)]:
            dv += 1 if p > m + 3 else (-1 if m > p + 3 else 0)
        if abs(mv) >= mw[int(len(mw) * 0.50)]:
            dv += 1 if mv > 0 else -1
        bullish = dv > 0

        if votes >= 2 and bullish:
            regime = '上行趋势'
        elif votes >= 2 and not bullish:
            regime = '下行趋势'
        elif votes == 1:
            regime = '偏多' if bullish else '偏空'
        else:
            regime = '震荡'

        result[i] = {
            'date': rows[i]['date'],
            'close': rows[i]['close'],
            'regime': regime,
            'votes': votes,
            'bullish': bullish
        }

    return result


def filter_trend_segments(regimes, min_dur=7):
    """标记持续≥min_dur天的上行/下行趋势段为'已确认'"""
    dates = [r['date'] for r in regimes if r]
    confirmed = {}

    i = 0
    while i < len(regimes):
        r = regimes[i]
        if r is None:
            i += 1
            continue
        if r['regime'] in ('上行趋势', '下行趋势'):
            j = i
            while j < len(regimes) and regimes[j] and regimes[j]['regime'] == r['regime']:
                j += 1
            dur = j - i
            if dur >= min_dur:
                for k in range(i, j):
                    confirmed[regimes[k]['date']] = True
            i = j
        else:
            i += 1

    return confirmed


def load_structure_signals(path):
    """加载深证成指 MACD 结构信号"""
    sigs = {}
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['index_name'] == '深证成指':
                sigs[row['date']] = {
                    'bottom_structure': int(row.get('bottom_structure', 0) or 0),
                    'top_structure': int(row.get('top_structure', 0) or 0),
                    'bottom_divergence': int(row.get('bottom_divergence', 0) or 0),
                    'top_divergence': int(row.get('top_divergence', 0) or 0),
                }
    return sigs


def load_sequence_events(path, dates_all):
    """加载深证成指月/周九转事件，月低9/高9前向延伸40天作为背景"""
    raw = defaultdict(lambda: {'月': None, '周': None})
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['index_name'] == '深证成指' and row['period'] in ('月', '周'):
                raw[row['date']][row['period']] = f"{row['direction']}{row['count']}"

    # 扩展月低9为40天背景窗口
    expanded = {}
    for d in dates_all:
        expanded[d] = {'月': None, '周': None}

    for d, v in raw.items():
        if v['月']:
            if d in expanded:
                expanded[d]['月'] = v['月']
            idx = dates_all.index(d) if d in dates_all else -1
            if idx >= 0:
                for j in range(idx, min(idx + 41, len(dates_all))):
                    if expanded[dates_all[j]]['月'] is None:
                        expanded[dates_all[j]]['月'] = f"{v['月']}背景"
        if v['周']:
            if d in expanded:
                expanded[d]['周'] = v['周']
            # 周低9延伸20天
            idx = dates_all.index(d) if d in dates_all else -1
            if idx >= 0 and '低' in v['周']:
                for j in range(idx, min(idx + 20, len(dates_all))):
                    if expanded[dates_all[j]]['周'] is None:
                        expanded[dates_all[j]]['周'] = f"{v['周']}背景"

    return expanded


def make_verdict(regimes, trend_confirmed, structure, sequence, dates):
    """
    核心裁决逻辑：
      "买入的原则要么突破趋势，要么底部结构形成" [20190812]
      "趋势为王，结构修边" [20190210]

    操作建议：
      持股 — 上行趋势中（已确认≥7天），结构没走完
      空仓 — 下行趋势中，或顶部结构形成
      观望 — 震荡市/不确定
      试探 — 底部结构形成，趋势尚未确认
    """
    verdicts = []

    for d in dates:
        r = next((x for x in regimes if x and x['date'] == d), None)
        sig = structure.get(d, {})
        seq_d = sequence.get(d, {})

        if not r:
            continue

        regime = r['regime']
        confirmed = trend_confirmed.get(d, False)
        bs = sig.get('bottom_structure', 0)
        ts = sig.get('top_structure', 0)
        month_seq = seq_d.get('月', '')
        week_seq = seq_d.get('周', '')

        # 裁决逻辑（2026-07-11 v2）
        # "趋势为王，结构修边" —— 趋势定仓位，结构不改动作只加备注
        # "买入的原则要么突破趋势，要么底部结构形成"
        # 偏多/偏空 = 有效趋势信号，不等"上行确认≥7天"

        is_bullish = regime in ('上行趋势', '偏多')
        is_bearish = regime in ('下行趋势', '偏空')
        month_bg = month_seq and '低9' in month_seq
        week_bg = week_seq and '低' in week_seq and '背景' in week_seq

        if is_bullish:
            if ts > 0:
                verdict = '持股'
                reason = '顶部结构形成(趋势未破)'
            else:
                verdict = '持股'
                reason = '趋势向上'
        elif is_bearish:
            if bs > 0 and (month_bg or week_bg):
                # 下行趋势+底部结构+月/周低9背景 → 试探
                bg = '月低9' if month_bg else '周低9'
                verdict = '试探'
                reason = f'底部结构+{bg}背景'
            elif bs > 0:
                verdict = '观望'
                reason = '底部结构+下行趋势(待趋势转)'
            else:
                verdict = '空仓'
                reason = '趋势向下'
        else:  # 震荡
            if bs > 0:
                verdict = '试探' if month_bg else '试探'
                reason = '底部结构+月低9背景' if month_bg else '底部结构+震荡'
            else:
                verdict = '观望'
                reason = '震荡市'

        verdicts.append({
            'date': d,
            'close': r['close'],
            'regime': regime,
            'trend_confirmed': 'Y' if confirmed else 'N',
            'bottom_structure': bs,
            'top_structure': ts,
            'month_seq': month_seq,
            'week_seq': week_seq,
            'verdict': verdict,
            'reason': reason
        })

    return verdicts


def main():
    import os
    from pathlib import Path
    base = str(Path(__file__).resolve().parent.parent / "data")

    print("═" * 60)
    print("  徐小明裁决引擎 v1.0")
    print("═" * 60)

    # 1. 加载数据
    print("\n[1/5] 加载数据...")
    rows = load_ohlc(f'{base}/daily_ma_channels.csv')
    structure = load_structure_signals(f'{base}/structure_signals.csv')
    print(f"  OHLC: {len(rows)} 天")
    print(f"  结构信号: {len(structure)} 天")

    # 2. 市况分类
    print("\n[2/5] 三合一市况分类...")
    regimes = compute_regime_classifier(rows)
    dates = sorted([r['date'] for r in regimes if r])

    # 3. 九转事件（月低9延伸40天背景）
    print("\n[3/5] 加载九转事件...")
    sequence = load_sequence_events(f'{base}/turn_sequence_events.csv', dates)
    print(f"  月低9/高9: {sum(1 for v in sequence.values() if v['月'])} 天（含40天背景延伸）")
    print(f"  周线事件: {sum(1 for v in sequence.values() if v['周'])} 天")

    # 4. 趋势确认
    print("\n[4/5] 趋势确认...")
    trend_confirmed = filter_trend_segments(regimes, min_dur=7)

    from collections import Counter
    cnt = Counter(r['regime'] for r in regimes if r)
    print(f"  市况分布: {dict(cnt)}")
    print(f"  趋势确认: {sum(trend_confirmed.values())} 天")

    # 4. 生成裁决
    print("\n[4/5] 生成裁决...")
    verdicts = make_verdict(regimes, trend_confirmed, structure, sequence, dates)

    vcnt = Counter(v['verdict'] for v in verdicts)
    print(f"  裁决分布: {dict(vcnt)}")

    # 5. 输出
    print(f"\n[5/5] 写入 data/verdict_daily.csv...")
    fieldnames = ['date', 'close', 'regime', 'trend_confirmed',
                  'bottom_structure', 'top_structure',
                  'month_seq', 'week_seq', 'verdict', 'reason']

    with open(f'{base}/verdict_daily.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(verdicts)

    print(f"  输出: {len(verdicts)} 天 ({verdicts[0]['date']} ~ {verdicts[-1]['date']})")

    # 摘要
    print("\n" + "═" * 60)
    print("  最近 10 天裁决")
    print("═" * 60)
    print(f"  {'日期':<12} {'收盘':<8} {'市况':<10} {'确认':<4} {'底结':<4} {'顶结':<4} {'裁决':<6}")
    print("  " + "─" * 55)
    for v in verdicts[-10:]:
        print(f"  {v['date']:<12} {v['close']:<8.0f} {v['regime']:<10} {v['trend_confirmed']:<4} "
              f"{v['bottom_structure']:<4} {v['top_structure']:<4} {v['verdict']:<6}")

    # 最新状态
    last = verdicts[-1]
    print(f"\n  当前状态 ({last['date']}):")
    print(f"    深证成指: {last['close']:.0f}")
    print(f"    市况: {last['regime']} {'(已确认)' if last['trend_confirmed']=='Y' else ''}")
    print(f"    结构: {'底结构形成' if last['bottom_structure'] else ''}{'顶结构形成' if last['top_structure'] else '无'}")
    print(f"    月九转: {last['month_seq'] or '无'}")
    print(f"    周九转: {last['week_seq'] or '无'}")
    print(f"    裁决: {last['verdict']} ({last['reason']})")


if __name__ == '__main__':
    main()
