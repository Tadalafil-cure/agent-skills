#!/usr/bin/env python3
"""
裁决引擎 v7
L1 月周九转 → L2-1 多指数共振 → L2-2/3 上证/深证独立裁决

并行架构：所有工具同时输出，裁决层综合。
"""
import csv, math, os
from datetime import datetime, timedelta
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 1. 数据加载
# ============================================================
def load_all_indices(path):
    """加载所有指数 OHLC + 结构信号，返回 {index_name: [rows]}"""
    data = defaultdict(list)
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = row['index_name']
            c = float(row['close'])
            if c <= 0: continue
            data[name].append({
                'date': row['date'], 'close': c,
                'high': float(row['high']), 'low': float(row['low']),
                'bottom_structure': int(row.get('bottom_structure', 0) or 0),
                'top_structure': int(row.get('top_structure', 0) or 0),
                'bottom_divergence': int(row.get('bottom_divergence', 0) or 0),
            })
    return data

def load_seq(path, index_name='深证成指'):
    """加载序列事件"""
    seq = defaultdict(dict)
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['index_name'] == index_name:
                seq[row['date']][row['period']] = row['seq_type']
    return seq

# ============================================================
# 2. 指标计算（三合一 + CHOP）
# ============================================================
def compute_indicators(rows, lookback=250):
    n = len(rows)
    if n < lookback: return [None] * n

    # ER(30)
    er30 = [0.0] * n
    for i in range(30, n):
        net = abs(rows[i]['close'] - rows[i-30]['close'])
        path = sum(abs(rows[j]['close'] - rows[j-1]['close']) for j in range(i-29, i+1))
        er30[i] = net / path if path > 0 else 0

    # ADX(14)
    period = 14
    tr_raw = [0.0] * n; pd_ = [0.0] * n; md = [0.0] * n
    for i in range(1, n):
        h, l = rows[i]['high'], rows[i]['low']
        ph, pl, pc = rows[i-1]['high'], rows[i-1]['low'], rows[i-1]['close']
        tr_raw[i] = max(h-l, abs(h-pc), abs(l-pc))
        up = h - ph; dn = pl - l
        pd_[i] = up if up > dn and up > 0 else 0
        md[i] = dn if dn > up and dn > 0 else 0

    def wilder(d, p):
        o = [0.0] * n
        for i in range(p, n):
            o[i] = sum(d[1:p+1]) if i == p else o[i-1] - o[i-1]/p + d[i]
        return o

    atr_w = wilder(tr_raw, period); pdi_w = wilder(pd_, period); mdi_w = wilder(md, period)
    adx_w = [0.0] * n; av = 0.0
    for i in range(period*2, n):
        pv = 100*pdi_w[i]/atr_w[i] if atr_w[i]>0 else 0
        mv = 100*mdi_w[i]/atr_w[i] if atr_w[i]>0 else 0
        dx = abs(pv-mv)/(pv+mv)*100 if (pv+mv)>0 else 0
        if av == 0:
            total = 0.0
            for j in range(i-period+1, i+1):
                pj = 100*pdi_w[j]/atr_w[j] if atr_w[j]>0 else 0
                mj = 100*mdi_w[j]/atr_w[j] if atr_w[j]>0 else 0
                dxj = abs(pj-mj)/(pj+mj)*100 if (pj+mj)>0 else 0
                total += dxj
            av = total/period if period>0 else 0
        else:
            av = (av*(period-1)+dx)/period
        adx_w[i] = av

    # 标准化动量(20)
    mom = [0.0] * n
    for i in range(20, n):
        ret = math.log(rows[i]['close']/rows[i-20]['close'])
        rets = [math.log(rows[j]['close']/rows[j-1]['close']) for j in range(i-19, i+1)]
        std = (sum(r*r for r in rets)/20)**0.5
        mom[i] = ret/(std*math.sqrt(20)) if std>0 else 0

    # CHOP(14)
    chop = [None] * n
    for i in range(13, n):
        ts = sum(tr_raw[i-13:i+1])
        hh = max(r['high'] for r in rows[i-13:i+1])
        ll = min(r['low'] for r in rows[i-13:i+1])
        chop[i] = 100*math.log10(ts/(hh-ll))/math.log10(14) if hh>ll else 100

    # 投票
    result = [None] * n
    for i in range(lookback, n):
        ew = sorted([er30[j] for j in range(i-lookback, i+1) if er30[j]>0])
        aw = sorted([adx_w[j] for j in range(i-lookback, i+1) if adx_w[j]>0])
        mw = sorted([abs(mom[j]) for j in range(i-lookback, i+1) if mom[j]!=0])
        if len(ew)<100: continue

        eth = ew[int(len(ew)*0.65)]; ath = aw[int(len(aw)*0.65)]; mth = mw[int(len(mw)*0.65)]
        er = er30[i]; adx = adx_w[i]; mv = mom[i]
        p = 100*pdi_w[i]/atr_w[i] if atr_w[i]>0 else 0
        m = 100*mdi_w[i]/atr_w[i] if atr_w[i]>0 else 0

        ve = 1 if er>=eth else 0; va = 1 if adx>=ath else 0; vm = 1 if abs(mv)>=mth else 0
        votes = ve+va+vm

        dv = 0
        if er >= ew[int(len(ew)*0.50)]: dv += 1 if rows[i]['close']>rows[i-30]['close'] else -1
        if adx >= aw[int(len(aw)*0.50)]: dv += 1 if p>m+3 else (-1 if m>p+3 else 0)
        if abs(mv) >= mw[int(len(mw)*0.50)]: dv += 1 if mv>0 else -1
        bullish = dv>0

        if votes>=2 and bullish: regime = '上行趋势'
        elif votes>=2 and not bullish: regime = '下行趋势'
        elif votes==1: regime = '偏多' if bullish else '偏空'
        else: regime = '震荡'

        result[i] = {
            'date': rows[i]['date'], 'close': rows[i]['close'],
            'regime': regime, 'chop': chop[i],
            'bullish': bullish, 'votes': votes,
            'bs': rows[i]['bottom_structure'], 'ts': rows[i]['top_structure'],
            'bd': rows[i]['bottom_divergence'],
        }
    return result

# ============================================================
# 3. 多指数共振
# ============================================================
def compute_resonance(indices_data):
    """
    indices_data: {name: [indicator_dicts]}
    返回: {date: {'bullish_count': N, 'bearish_count': N, 'resonance': str}}
    """
    date_map = defaultdict(dict)
    for name, data in indices_data.items():
        for r in data:
            if r is None: continue
            # bullish: explicitly True; bearish: explicitly False; neutral: None/other
            if r['regime'] in ('上行趋势', '偏多'):
                date_map[r['date']][name] = True
            elif r['regime'] in ('下行趋势', '偏空'):
                date_map[r['date']][name] = False
            # 震荡 → no vote

    resonance = {}
    for d, idx_votes in date_map.items():
        bulls = sum(1 for b in idx_votes.values() if b is True)
        bears = sum(1 for b in idx_votes.values() if b is False)
        total = len(idx_votes)

        if total < 3: continue

        if bulls >= 4: res = '强共振_上升'
        elif bears >= 4: res = '强共振_下跌'
        elif bulls == 3 and bears == 0: res = '偏共振_偏多'
        elif bears == 3 and bulls == 0: res = '偏共振_偏空'
        elif bulls >= 2 and bears >= 2: res = '分化'
        elif bulls == 3: res = '偏共振_偏多'
        elif bears == 3: res = '偏共振_偏空'
        else: res = '混合'

        resonance[d] = {'bullish_count': bulls, 'bearish_count': bears,
                        'resonance': res, 'total': total}
    return resonance

# ============================================================
# 4. 单指数裁决
# ============================================================
def chop_level(c):
    if c is None: return 'unknown'
    if c < 38.2: return 'clear'
    if c <= 61.8: return 'fuzzy'
    return 'chaotic'

def is_trending(regime, cl):
    """判断是否趋势期"""
    if cl == 'chaotic': return False  # 混乱强制归震荡
    if regime in ('上行趋势', '偏多', '下行趋势', '偏空'): return True
    return False

def bs_filter_passed(rows, idx, indicators):
    """底部结构综合筛选 — 简化版，保证不丢信号"""
    i = idx
    if i < 120: return False  # need 120 days warmup

    # 回撤：取 60日和120日 中更深的一个
    peak60 = max(r['close'] for r in rows[max(0,i-60):i+1])
    peak120 = max(r['close'] for r in rows[max(0,i-120):i+1])
    curr = rows[i]['close']
    dd60 = (curr / peak60 - 1) * 100
    dd120 = (curr / peak120 - 1) * 100
    best_dd = min(dd60, dd120)  # more negative = deeper drawdown

    # 恐慌底标准: 深跌+不拥挤
    bs_recent = sum(1 for j in range(max(0, i-30), i)
                   if rows[j].get('bottom_structure', 0))
    if best_dd <= -15 and bs_recent <= 2:
        return True
    # 磨底标准: 中度回撤+允许簇
    if best_dd <= -8 and bs_recent <= 6:
        return True
    return False

def bs_pattern(chop_val, chop_hist):
    had_high = max(chop_hist) > 60 if chop_hist else False
    if chop_val is None: return '试探', '底结构'
    if chop_val < 40 and had_high: return '试探(恐慌底)', f'CHOP={chop_val:.0f}<40+前高CHOP'
    if chop_val > 61.8: return '试探(衰竭底)', f'CHOP={chop_val:.0f}>62衰竭'
    return '试探(磨底)', f'CHOP={chop_val:.0f}(磨底)'

def verdict_single(indicators, rows, resonance, seq_data):
    """单指数裁决，返回裁决列表"""
    n = len(indicators)
    results = [None] * n

    # Pre-compute resonance lookup
    res_map = {d: r['resonance'] for d, r in resonance.items()}

    for i in range(n):
        r = indicators[i]
        if r is None: continue
        d = r['date']; c = r['chop']
        if c is None: continue

        cl = chop_level(c); regime = r['regime']
        trending = is_trending(regime, cl)
        bullish = r['bullish']

        # bs/ts recent + bs_ok tracking
        bs_today = r['bs']; ts_today = r['ts']
        bs_recent = any(rows[j].get('bottom_structure', 0) for j in range(max(0,i-3), i+1))
        ts_recent = any(rows[j].get('top_structure', 0) for j in range(max(0,i-5), i+1))

        # BS filter: check on the actual structure day
        bs_ok = bs_filter_passed(rows, i, indicators) if bs_today else False
        # For bs_recent, check if ANY recent bs day passed the filter
        bs_ok_recent = False
        if not bs_ok and bs_recent:
            for j in range(max(0,i-3), i+1):
                if rows[j].get('bottom_structure', 0) and bs_filter_passed(rows, j, indicators):
                    bs_ok_recent = True
                    break
        bs_ok = bs_ok or bs_ok_recent

        # Day seq
        day_seq = seq_data.get(d, {}).get('日线')

        # Month/week low9 windows
        dt = datetime.strptime(d, '%Y-%m-%d')
        in_month = any(cd in seq_data and '月线' in seq_data[cd]
                       for j in range(60)
                       for cd in [(dt - timedelta(days=j)).strftime('%Y-%m-%d')]
                       if j <= 40) if any(True for _ in [0]) else False
        in_week = False
        for j in range(30):
            cd = (dt - timedelta(days=j)).strftime('%Y-%m-%d')
            if cd in seq_data and '周线' in seq_data[cd]:
                if j <= 20: in_week = True
                break
        in_month = False  # reset, do properly
        for j in range(60):
            cd = (dt - timedelta(days=j)).strftime('%Y-%m-%d')
            if cd in seq_data and '月线' in seq_data[cd]:
                if j <= 40: in_month = True
                break

        # CHOP history
        chop_hist = [indicators[j]['chop'] for j in range(max(0,i-20), i+1)
                     if indicators[j] and indicators[j]['chop'] is not None]

        # CHOP trend (5-day)
        recent5 = [ch for ch in chop_hist[-5:] if ch is not None]
        chop_rising = len(recent5) >= 5 and c > sum(recent5)/len(recent5) + 3
        chop_falling = len(recent5) >= 5 and c < sum(recent5)/len(recent5) - 5

        # Resonance
        res = res_map.get(d, '混合')
        strong_bull = res == '强共振_上升'
        strong_bear = res == '强共振_下跌'

        # BS filter
        bs_ok = bs_filter_passed(rows, i, indicators) if bs_today else False

        # 顶结构计数：当前上升段内第几次
        # 追踪从最近一次 regime 转 bullish 以来的顶结构次数
        ts_count = 0
        for j in range(i, -1, -1):
            if indicators[j] is None: continue
            if not indicators[j]['bullish']: break  # 上升段结束
            if rows[j].get('top_structure', 0):
                ts_count += 1
        # ts_recent 也算（可能跨了几天）
        if ts_today and ts_count == 0:
            ts_count = 1  # today's structure

        # ============ 裁决 ============
        verdict = '观望'; reason = ''

        if trending:
            # --- 趋势期 ---
            if bullish:
                verdict = '持股'; reason = '趋势向上'
                if (ts_today or ts_recent) and ts_count >= 2:
                    verdict = '减仓'; reason = f'趋势+第{ts_count}次顶结构→减仓'
                elif ts_today or ts_recent:
                    verdict = '持股(警戒)'; reason = '趋势+顶结构→警戒'
                elif day_seq == '高9':
                    verdict = '持股(警戒)'; reason = '趋势+高9→警戒'
            else:
                verdict = '空仓'; reason = '趋势向下'
                if (bs_today and bs_ok) or (bs_recent and bs_ok):
                    tag, rsn = bs_pattern(c, chop_hist)
                    if in_month: tag = tag.replace('试探','持股')+'+月低9'; rsn += '+月低9'
                    elif in_week: tag = tag.replace('试探','持股')+'+周低9'; rsn += '+周低9'
                    verdict = tag; reason = rsn
                elif day_seq == '低9':
                    verdict = '空仓(关注)'; reason = '趋势向下+低9→关注'

            # 共振调整
            if strong_bull and not bullish:
                verdict = '试探'; reason = '强共振上升+单指数偏空→试探'
            if strong_bear and bullish:
                verdict = '持股(警戒)'; reason = '强共振下跌+单指数偏多→警戒'

        else:
            # --- 震荡期 ---
            if (bs_today and bs_ok) or (bs_recent and bs_ok):
                tag, rsn = bs_pattern(c, chop_hist)
                if in_month: tag = tag.replace('试探','持股')+'+月低9'; rsn += '+月低9'
                elif in_week: tag = tag.replace('试探','持股')+'+周低9'; rsn += '+周低9'
                verdict = tag; reason = rsn
            elif ts_today or ts_recent:
                verdict = '空仓'; reason = '震荡+顶结构→空仓'
            elif chop_falling and bullish:
                verdict = '试探'; reason = 'CHOP收敛+方向转正→等突破'
                if strong_bull: verdict = '持股'; reason += '+强共振上升'
            elif day_seq == '高9':
                verdict = '观望(偏空)'; reason = '震荡+高9'
            elif day_seq == '低9':
                verdict = '观望(偏多)'; reason = '震荡+低9'
            else:
                verdict = '观望'; reason = '震荡'

        results[i] = {
            'date': d, 'close': r['close'], 'regime': regime,
            'chop': c, 'chop_level': cl, 'trending': trending,
            'bs': bs_today, 'ts': ts_today, 'bs_ok': bs_ok,
            'day_seq': day_seq or '', 'month_win': in_month, 'week_win': in_week,
            'chop_rising': chop_rising, 'chop_falling': chop_falling,
            'resonance': res, 'strong_bull': strong_bull, 'strong_bear': strong_bear,
            'verdict': verdict, 'reason': reason
        }
    return results

# ============================================================
# 5. 主程序
# ============================================================
def main():
    all_data = load_all_indices(os.path.join(BASE, 'data/structure_signals.csv'))
    print(f'加载指数: {list(all_data.keys())}')

    # 计算所有指数指标
    indices_indicators = {}
    for name, rows in all_data.items():
        indices_indicators[name] = compute_indicators(rows)
        print(f'  {name}: {sum(1 for x in indices_indicators[name] if x)} 天')

    # 多指数共振
    resonance = compute_resonance(indices_indicators)
    print(f'共振天数: {len(resonance)}')

    # 加载序列（深证和上证分别）
    seq_sz = load_seq(os.path.join(BASE, 'data/turn_sequence_events.csv'), '深证成指')
    seq_sh = load_seq(os.path.join(BASE, 'data/turn_sequence_events.csv'), '上证指数')

    # 单指数裁决
    verdict_sz = verdict_single(indices_indicators['深证成指'], all_data['深证成指'], resonance, seq_sz)
    verdict_sh = verdict_single(indices_indicators['上证指数'], all_data['上证指数'], resonance, seq_sh)

    # 输出
    out_path = os.path.join(BASE, 'data/verdict_v7.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        headers = ['date', 'close_sz', 'close_sh',
                   'regime_sz', 'regime_sh', 'chop_sz', 'chop_sh', 'chop_level',
                   'resonance', 'strong_bull', 'strong_bear',
                   'bs_sz', 'ts_sz', 'bs_sh', 'ts_sh',
                   'bs_ok_sz', 'bs_ok_sh',
                   'day_seq_sz', 'day_seq_sh', 'month_win', 'week_win',
                   'verdict_sz', 'verdict_sh', 'verdict_final', 'reason']
        w.writerow(headers)

        for i in range(len(verdict_sz)):
            vs = verdict_sz[i]; vh = verdict_sh[i]
            if vs is None and vh is None: continue

            d = (vs or vh)['date']
            close_sz = vs['close'] if vs else ''
            close_sh = vh['close'] if vh else ''
            regime_sz = vs['regime'] if vs else ''
            regime_sh = vh['regime'] if vh else ''
            chop_sz = f"{vs['chop']:.1f}" if vs and vs['chop'] else ''
            chop_sh = f"{vh['chop']:.1f}" if vh and vh['chop'] else ''
            cl = (vs or vh)['chop_level']
            res = (vs or vh)['resonance']
            sb = (vs or vh)['strong_bull']; sbe = (vs or vh)['strong_bear']

            bs_sz = vs['bs'] if vs else ''; ts_sz = vs['ts'] if vs else ''
            bs_sh = vh['bs'] if vh else ''; ts_sh = vh['ts'] if vh else ''
            bs_ok_sz = vs['bs_ok'] if vs else ''; bs_ok_sh = vh['bs_ok'] if vh else ''
            ds_sz = (vs or {}).get('day_seq', '')
            ds_sh = (vh or {}).get('day_seq', '')
            mw = (vs or vh)['month_win']; ww = (vs or vh)['week_win']

            v_sz = vs['verdict'] if vs else ''; v_sh = vh['verdict'] if vh else ''

            # 综合裁决：2024前深证为主，2024起上证权重50%
            # 规则：有试探/持股的指数优先于空仓/观望的指数
            yr = int(d[:4])
            def signal_strength(v):
                if '减仓' in v: return 5           # 减仓是最强信号
                if '持股' in v and '警戒' not in v: return 4
                if '持股(警戒)' in v: return 3
                if '试探' in v: return 2
                if '观望' in v: return 1
                return 0  # 空仓
            
            if yr < 2024:
                v_final = v_sz; rsn = vs['reason'] if vs else ''
                # 但如果上证有底部结构信号而深证没有，跟上证
                if (vh and ('试探' in v_sh or '持股' in v_sh)) and ('试探' not in v_sz and '持股' not in v_sz):
                    if bs_ok_sh:
                        v_final = v_sh
                        rsn = 'SH:' + (vh['reason'] if vh else '')
            else:
                # 取更强的信号（试探>空仓，持股>观望）
                ss_sz = signal_strength(v_sz); ss_sh = signal_strength(v_sh)
                if ss_sh > ss_sz:
                    v_final = v_sh; rsn = f'SH:{vh["reason"]}' if vh else ''
                elif ss_sz > ss_sh:
                    v_final = v_sz; rsn = f'SZ:{vs["reason"]}' if vs else ''
                else:
                    # 同等级取更保守
                    def conservatism(v):
                        if '持股' in v and '警戒' not in v: return 3
                        if '持股(警戒)' in v: return 2
                        if '试探' in v: return 1
                        if '观望' in v: return 0
                        return -1
                    if conservatism(v_sz) < conservatism(v_sh):
                        v_final = v_sz; rsn = f'SZ:{vs["reason"]}' if vs else ''
                    else:
                        v_final = v_sh; rsn = f'SH:{vh["reason"]}' if vh else ''

            w.writerow([d, close_sz, close_sh, regime_sz, regime_sh, chop_sz, chop_sh, cl,
                        res, sb, sbe, bs_sz, ts_sz, bs_sh, ts_sh,
                        bs_ok_sz, bs_ok_sh, ds_sz, ds_sh, mw, ww,
                        v_sz, v_sh, v_final, rsn])

    print(f'\n裁决引擎v7: {out_path}')
    # Quick stats
    vc = Counter(); rsc = Counter()
    with open(out_path) as f:
        for row in csv.DictReader(f):
            v = row['verdict_final']
            if '持股' in v and '警戒' not in v: vc['持股类'] += 1
            elif '持股(警戒)' in v: vc['警戒'] += 1
            elif '减仓' in v: vc['减仓'] += 1
            elif '试探' in v: vc['试探类'] += 1
            elif '空仓' in v: vc['空仓'] += 1
            else: vc['观望类'] += 1
            rsc[row['resonance']] += 1
    total = sum(vc.values())
    print(f'总交易日: {total}')
    print(f'\n综合裁决:')
    for k, v in vc.most_common(): print(f'  {k}: {v}天 ({v/total*100:.0f}%)')
    print(f'\n共振分布:')
    for k, v in rsc.most_common(): print(f'  {k}: {v}天 ({v/total*100:.0f}%)')

if __name__ == '__main__':
    main()
