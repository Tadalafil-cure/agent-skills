#!/usr/bin/env python3
"""
裁决引擎 v7 · 四指数独立 + 双共振
L1 月周九转 → L2-1 五指数共振 → L2-2/3/4/5 上证/深证/创业板/科创50 独立裁决
L2-6 创业板+科创50 双指数共振

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

    er30 = [0.0] * n
    for i in range(30, n):
        net = abs(rows[i]['close'] - rows[i-30]['close'])
        path = sum(abs(rows[j]['close'] - rows[j-1]['close']) for j in range(i-29, i+1))
        er30[i] = net / path if path > 0 else 0

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

    mom = [0.0] * n
    for i in range(20, n):
        ret = math.log(rows[i]['close']/rows[i-20]['close'])
        rets = [math.log(rows[j]['close']/rows[j-1]['close']) for j in range(i-19, i+1)]
        std = (sum(r*r for r in rets)/20)**0.5
        mom[i] = ret/(std*math.sqrt(20)) if std>0 else 0

    chop = [None] * n
    for i in range(13, n):
        ts = sum(tr_raw[i-13:i+1])
        hh = max(r['high'] for r in rows[i-13:i+1])
        ll = min(r['low'] for r in rows[i-13:i+1])
        chop[i] = 100*math.log10(ts/(hh-ll))/math.log10(14) if hh>ll else 100

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
    date_map = defaultdict(dict)
    for name, data in indices_data.items():
        for r in data:
            if r is None: continue
            if r['regime'] in ('上行趋势', '偏多'):
                date_map[r['date']][name] = True
            elif r['regime'] in ('下行趋势', '偏空'):
                date_map[r['date']][name] = False

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


def compute_cyb_kc_resonance(indicators_cyb, indicators_kc):
    """创业板+科创50 双指数共振"""
    date_map = defaultdict(dict)
    for r in indicators_cyb:
        if r is None: continue
        if r['regime'] in ('上行趋势', '偏多'):
            date_map[r['date']]['创业板指'] = True
        elif r['regime'] in ('下行趋势', '偏空'):
            date_map[r['date']]['创业板指'] = False

    for r in indicators_kc:
        if r is None: continue
        if r['regime'] in ('上行趋势', '偏多'):
            date_map[r['date']]['科创50'] = True
        elif r['regime'] in ('下行趋势', '偏空'):
            date_map[r['date']]['科创50'] = False

    result = {}
    for d, votes in date_map.items():
        bull = votes.get('创业板指', None)
        bear = votes.get('科创50', None)
        if bull is None or bear is None: continue
        if bull and bear: res = '共振_偏多'
        elif not bull and not bear: res = '共振_偏空'
        elif bull != bear: res = '分化'
        else: res = '混合'
        result[d] = res
    return result


# ============================================================
# 4. 单指数裁决
# ============================================================
def chop_level(c):
    """CHOP 三级分档（非对称滞回设计）
    
    CHOP > 61.8 (chaotic): 单日即切→震荡。
        回测依据(2021-2026, 科创50 1329天):
        - 18个>61.8簇，36.7%为单日尖刺
        - 滞回(N=2/N=3)拖后腿: 延迟18天多亏+16.10%
        - 即时切换 Sharpe=0.31 vs 滞回=0.22
        - 原因: 上穿61.8是真正的恐慌/分歧爆发, 即使次日回落当天也真跌
        
    CHOP < 38.2 (clear): ≥3天持续确认才有效。
        回测依据(同数据源):
        - 94%单日跌破38.2为假收敛(触及即弹回)
        - ≥3天持续<38.2: 10次信号 20日胜率70% +2.1%
        - ≥1天: 胜率仅58% +1.1%, 噪声主导
        
    两条线的不对称不是bug——上穿是真信号多假信号少, 下穿是假信号多真信号少。
    """
    if c is None: return 'unknown'
    if c < 38.2: return 'clear'
    if c <= 61.8: return 'fuzzy'
    return 'chaotic'

def is_trending(regime, cl):
    """趋势判定: CHOP>61.8(chaotic)→直接否趋势, 无滞回, 单日即切。
    
    这与 CHOP<38.2 的 ≥3天滞回形成非对称设计:
    - 上穿61.8: 即时切换 (真信号多, 滞回代价大)
    - 下穿38.2: ≥3天确认 (假信号多, 需持续验证)
    """
    if cl == 'chaotic': return False
    if regime in ('上行趋势', '偏多', '下行趋势', '偏空'): return True
    return False

def bs_filter_passed(rows, idx, indicators):
    i = idx
    if i < 120: return False

    peak60 = max(r['close'] for r in rows[max(0,i-60):i+1])
    peak120 = max(r['close'] for r in rows[max(0,i-120):i+1])
    curr = rows[i]['close']
    dd60 = (curr / peak60 - 1) * 100
    dd120 = (curr / peak120 - 1) * 100
    best_dd = min(dd60, dd120)

    bs_recent = sum(1 for j in range(max(0, i-30), i)
                   if rows[j].get('bottom_structure', 0))
    if best_dd <= -15 and bs_recent <= 2:
        return True
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
    n = len(indicators)
    results = [None] * n
    res_map = {d: r['resonance'] for d, r in resonance.items()}

    # === 震荡来路检测（v4.6.1新增）===
    def detect_oscillation_origin(idx):
        """回看当前震荡段之前最后一个 ≥7天 的趋势段方向。
        返回 '上行'/'下行'/None。"""
        # Step 1: 找到当前震荡段的起点（连续震荡往前追溯）
        osc_start = idx
        for j in range(idx, max(0, idx-200), -1):
            if indicators[j] is None: break
            r_prev = indicators[j]['regime']
            cl_prev = chop_level(indicators[j]['chop'])
            if r_prev not in ('震荡',) and not is_trending(r_prev, cl_prev):
                continue  # still non-trending
            if r_prev in ('上行趋势', '偏多', '下行趋势', '偏空'):
                osc_start = j + 1
                break
            elif r_prev == '震荡':
                osc_start = j
            else:
                break

        # Step 2: 从震荡起点往前找 ≥7天 的趋势段
        seg_start = None
        seg_dir = None
        seg_days = 0
        for j in range(osc_start-1, max(0, osc_start-200), -1):
            if indicators[j] is None: break
            r_prev = indicators[j]['regime']
            if r_prev in ('上行趋势', '偏多'):
                if seg_dir is None:
                    seg_dir = '上行'
                    seg_start = j
                if seg_dir == '上行':
                    seg_days += 1
                else:
                    break  # 方向变了
            elif r_prev in ('下行趋势', '偏空'):
                if seg_dir is None:
                    seg_dir = '下行'
                    seg_start = j
                if seg_dir == '下行':
                    seg_days += 1
                else:
                    break
            else:  # 震荡
                if seg_dir is not None:
                    break  # 趋势段结束

        if seg_dir and seg_days >= 7:
            return seg_dir
        return None

    for i in range(n):
        r = indicators[i]
        if r is None: continue
        d = r['date']; c = r['chop']
        if c is None: continue

        cl = chop_level(c); regime = r['regime']
        trending = is_trending(regime, cl)
        bullish = r['bullish']

        bs_today = r['bs']; ts_today = r['ts']
        bs_recent = any(rows[j].get('bottom_structure', 0) for j in range(max(0,i-3), i+1))
        ts_recent = any(rows[j].get('top_structure', 0) for j in range(max(0,i-5), i+1))

        bs_ok = bs_filter_passed(rows, i, indicators) if bs_today else False
        bs_ok_recent = False
        if not bs_ok and bs_recent:
            for j in range(max(0,i-3), i+1):
                if rows[j].get('bottom_structure', 0) and bs_filter_passed(rows, j, indicators):
                    bs_ok_recent = True
                    break
        bs_ok = bs_ok or bs_ok_recent

        day_seq = seq_data.get(d, {}).get('日线')

        # 顶结构计数
        ts_count = 0
        for j in range(i, -1, -1):
            if indicators[j] is None: continue
            if not indicators[j]['bullish']: break
            if rows[j].get('top_structure', 0):
                ts_count += 1
        if ts_today and ts_count == 0:
            ts_count = 1

        # 月周低9窗口
        dt = datetime.strptime(d, '%Y-%m-%d')
        in_month = False
        for j in range(60):
            cd = (dt - timedelta(days=j)).strftime('%Y-%m-%d')
            if cd in seq_data and '月线' in seq_data[cd]:
                if j <= 40: in_month = True
                break
        in_week = False
        for j in range(30):
            cd = (dt - timedelta(days=j)).strftime('%Y-%m-%d')
            if cd in seq_data and '周线' in seq_data[cd]:
                if j <= 20: in_week = True
                break

        chop_hist = [indicators[j]['chop'] for j in range(max(0,i-20), i+1)
                     if indicators[j] and indicators[j]['chop'] is not None]
        recent5 = [ch for ch in chop_hist[-5:] if ch is not None]
        chop_falling = len(recent5) >= 5 and c < sum(recent5)/len(recent5) - 5

        # v4.6.1: CHOP持续<38.2检测（≥3天，最优阈值：70%胜率 +2.1%）
        chop_sustained_clear = len(chop_hist) >= 3 and all(ch is not None and ch < 38.2 for ch in chop_hist[-3:])
        chop_below_38 = c is not None and c < 38.2  # 单日关注信号

        res = res_map.get(d, '混合')
        strong_bull = res == '强共振_上升'
        strong_bear = res == '强共振_下跌'

        # === 震荡来路判断 ===
        osc_origin = detect_oscillation_origin(i) if not trending else None

        # ============ 裁决 ============
        verdict = '观望'; reason = ''

        if trending:
            if bullish:
                verdict = '持股'; reason = '趋势向上'
                if (ts_today or ts_recent) and ts_count >= 2:
                    verdict = '减仓'; reason = f'趋势+第{ts_count}次顶结构→减仓'
                elif ts_today or ts_recent:
                    verdict = '持股(警戒)'; reason = '趋势+顶结构→警戒'
                elif day_seq == '高9':
                    verdict = '持股(警戒)'; reason = '趋势+高9→警戒'
                # v4.6.2: CHOP > 55 趋势可信度告警——距61.8切换线越近风险越高
                if verdict == '持股' and c is not None and c > 55:
                    gap = 61.8 - c
                    reason += f' | ⚠️CHOP={c:.0f}(距61.8切换线仅{gap:.1f}点)'
            else:
                verdict = '空仓'; reason = '趋势向下'
                if (bs_today and bs_ok) or (bs_recent and bs_ok):
                    tag, rsn = bs_pattern(c, chop_hist)
                    if in_month: tag = tag.replace('试探','持股')+'+月低9'; rsn += '+月低9'
                    elif in_week: tag = tag.replace('试探','持股')+'+周低9'; rsn += '+周低9'
                    verdict = tag; reason = rsn
                elif day_seq == '低9':
                    verdict = '空仓(关注)'; reason = '趋势向下+低9→关注'

            if strong_bull and not bullish:
                verdict = '试探'; reason = '强共振上升+单指数偏空→试探'
            if strong_bear and bullish:
                verdict = '持股(警戒)'; reason = '强共振下跌+单指数偏多→警戒'
        else:
            # 震荡市（v4.6.1 震荡框架）
            # 规则优先级: BS+filter(下行来路) > CHOP收敛 > 序列信号 > 来路默认
            # v4.6.13: 上行来路震荡中底结构不独立触发操作——仅关注，等出口方向或趋势突破
            #   - 上行来路: 顶结构已减仓，底结构是反弹不是反转，不抄底
            #   - 下行来路: 空仓等入场，底结构是唯一标准，BS筛选通过→试探
            #   - 来路不明: 保守处理，不触发
            if (bs_today and bs_ok) or (bs_recent and bs_ok):
                if osc_origin == '上行':
                    verdict = '观望'; reason = '来路上行+底结构→关注(不触发)'
                    if in_month: reason += '+月低9'
                    if day_seq == '低9': verdict = '观望(偏多)'; reason += '+低9'
                elif osc_origin == '下行':
                    tag, rsn = bs_pattern(c, chop_hist)
                    if in_month: tag = tag.replace('试探','持股')+'+月低9'; rsn += '+月低9'
                    elif in_week: tag = tag.replace('试探','持股')+'+周低9'; rsn += '+周低9'
                    verdict = tag; reason = rsn
                else:
                    verdict = '观望'; reason = '来路不明+底结构→观望'
                    if in_month: reason += '+月低9'
            elif chop_sustained_clear and bullish:
                verdict = '试探'; reason = 'CHOP持续<38.2(≥3天)+方向偏多→试探'
                if strong_bull: verdict = '持股'; reason += '+强共振上升'
            elif day_seq == '高9':
                verdict = '观望(偏空)'; reason = '震荡+高9'
            elif day_seq == '低9':
                verdict = '观望(偏多)'; reason = '震荡+低9'
            else:
                # v4.6.1: 震荡来路判断（H17）
                # v4.6.2: CHOP>61.8 硬切换明确标注——不是"趋势降级"是策略翻牌
                if osc_origin == '上行':
                    verdict = '观望(偏多)'; reason = '震荡，来路上行→偏多'
                elif osc_origin == '下行':
                    verdict = '观望'; reason = '震荡，来路下行→观望'
                else:
                    verdict = '观望'; reason = '震荡'
                # CHOP原因标注
                if c is not None and c > 61.8:
                    reason += f' | CHOP={c:.0f}>61.8硬切换(趋势→震荡)'
                # CHOP<38.2 单日关注（不触发操作，仅标注）
                elif chop_below_38 and not chop_sustained_clear:
                    reason += ' | CHOP<38.2关注'

        results[i] = {
            'date': d, 'close': r['close'], 'regime': regime,
            'chop': c, 'chop_level': cl, 'trending': trending,
            'bs': bs_today, 'ts': ts_today, 'bd': r.get('bd', 0), 'bs_ok': bs_ok,
            'day_seq': day_seq or '', 'month_win': in_month, 'week_win': in_week,
            'resonance': res, 'strong_bull': strong_bull, 'strong_bear': strong_bear,
            'osc_origin': osc_origin or '',
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

    # 五指数共振（排除科创50，避免稀释大盘信号）
    indices_five = {k: v for k, v in indices_indicators.items() if k != '科创50'}
    resonance = compute_resonance(indices_five)
    print(f'五指数共振天数: {len(resonance)}')

    # 创业板+科创50 双指数共振（格式化为与五指数共振相同）
    cyb_kc_res_raw = compute_cyb_kc_resonance(
        indices_indicators.get('创业板指', []),
        indices_indicators.get('科创50', [])
    )
    cyb_kc_res = {d: {'resonance': v, 'bullish_count': 0, 'bearish_count': 0, 'total': 2}
                  for d, v in cyb_kc_res_raw.items()}
    print(f'创业板+科创50共振天数: {len(cyb_kc_res)}')

    # v4.6.13: 提取沪深300/中证500 regime 供五指数投票明细
    regime_300 = {}; regime_500 = {}
    for name, indicators in indices_indicators.items():
        if name == '沪深300':
            for r in indicators:
                if r: regime_300[r['date']] = r['regime']
        elif name == '中证500':
            for r in indicators:
                if r: regime_500[r['date']] = r['regime']
    print(f'沪深300 regime: {len(regime_300)}天, 中证500 regime: {len(regime_500)}天')

    # 加载序列
    seq_path = os.path.join(BASE, 'data/turn_sequence_events.csv')
    seq_sz = load_seq(seq_path, '深证成指')
    seq_sh = load_seq(seq_path, '上证指数')
    seq_cyb = load_seq(seq_path, '创业板指')
    seq_kc = load_seq(seq_path, '科创50')

    # 四指数独立裁决
    # 主板：上证+深证，使用五指数共振
    vs = verdict_single(indices_indicators['深证成指'], all_data['深证成指'], resonance, seq_sz)
    vh = verdict_single(indices_indicators['上证指数'], all_data['上证指数'], resonance, seq_sh)
    # 科技：创业板+科创50，使用双创共振（独立的科技市场信号）
    vc = verdict_single(indices_indicators['创业板指'], all_data['创业板指'], cyb_kc_res, seq_cyb)
    vk = verdict_single(indices_indicators['科创50'], all_data['科创50'], cyb_kc_res, seq_kc)

    # 对齐长度
    max_len = max(len(vs), len(vh), len(vc), len(vk))
    for arr in [vs, vh, vc, vk]:
        while len(arr) < max_len:
            arr.insert(0, None)

    # 输出
    out_path = os.path.join(BASE, 'data/verdict_v7.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        headers = [
            'date',
            'close_sz', 'close_sh', 'close_cyb', 'close_kc',
            'regime_sz', 'regime_sh', 'regime_cyb', 'regime_kc',
            'regime_hs300', 'regime_zz500',
            'chop_sz', 'chop_sh', 'chop_cyb', 'chop_kc',
            'resonance', 'strong_bull', 'strong_bear',
            'cyb_kc_resonance',
            'bs_sz', 'ts_sz', 'bs_sh', 'ts_sh', 'bs_cyb', 'ts_cyb', 'bs_kc', 'ts_kc',
            'bd_sz', 'bd_sh', 'bd_cyb', 'bd_kc',
            'bs_ok_sz', 'bs_ok_sh', 'bs_ok_cyb', 'bs_ok_kc',
            'day_seq_sz', 'day_seq_sh', 'day_seq_cyb', 'day_seq_kc',
            'month_win', 'week_win',
            'osc_origin_sz', 'osc_origin_sh',
            'verdict_sz', 'verdict_sh', 'verdict_cyb', 'verdict_kc',
            'reason_sz', 'reason_sh', 'reason_cyb', 'reason_kc',
            'verdict_main', 'verdict_tech', 'reason'
        ]
        w.writerow(headers)

        for i in range(len(vs)):
            row_sz = vs[i]; row_sh = vh[i]; row_cyb = vc[i]; row_kc = vk[i]
            if all(x is None for x in [row_sz, row_sh, row_cyb, row_kc]): continue

            d = (row_sz or row_sh or row_cyb or row_kc)['date']

            def vf(r, k): return r[k] if r else ''
            def vfi(r, k): return r[k] if r else 0
            def vfs(r, k, fmt='.1f'):
                v = r[k] if r else None
                return f'{v:{fmt}}' if v is not None else ''

            res = (row_sz or row_sh or row_cyb or row_kc)['resonance']
            sb = (row_sz or row_sh or row_cyb or row_kc)['strong_bull']
            sbe = (row_sz or row_sh or row_cyb or row_kc)['strong_bear']
            ckr = cyb_kc_res.get(d, {}).get('resonance', '混合')
            mw = (row_sz or row_sh or row_cyb or row_kc)['month_win']
            ww = (row_sz or row_sh or row_cyb or row_kc)['week_win']

            v_sz = vf(row_sz, 'verdict'); v_sh = vf(row_sh, 'verdict')
            v_cyb = vf(row_cyb, 'verdict'); v_kc = vf(row_kc, 'verdict')

            # ============================================================
            # 共振驱动裁决（v4.6.11）
            # 主板 = 五指数共振投票结果，上证/深证单指数裁决为辅助参考
            # 科技 = 双创共振投票结果，创业板/科创50单指数裁决为辅助参考
            # 单指数裁决不冒充共振共识。R5.2: 混合/分化时各指数各自判断，但标注"共振无方向"
            # ============================================================

            # 五指数共振 → 主板裁决
            bulls5 = resonance.get(d, {}).get('bullish_count', 0)
            bears5 = resonance.get(d, {}).get('bearish_count', 0)
            total5 = resonance.get(d, {}).get('total', 5)

            resonance_to_verdict = {
                '强共振_上升': '持股',
                '强共振_下跌': '空仓',
                '偏共振_偏多': '观望(偏多)',
                '偏共振_偏空': '观望(偏空)',
                '分化': '观望',
                '混合': '观望',
            }
            v_main = resonance_to_verdict.get(res, '观望')
            rsn_main = f'五指数{bulls5}:{bears5}({res})'

            # 双创共振 → 科技裁决（v4.6.11）
            # 架构：科创50定方向 → 双创共振定升降档
            #   共振_偏多/偏空（两人一致）→ 维持科创50强度
            #   分化/混合（两人不一致）→ 创业板不同意见 → 降档一级
            # 科技与主板独立裁决——科技共振不依赖五指数共振
            res_ck = ckr
            v_kc_base = str(v_kc) if v_kc else '观望'

            # 降档映射：创业板不同意 → 科创50强度降一级
            downgrade = {
                '持股': '持股(警戒)',
                '持股(警戒)': '观望(偏多)',
                '试探': '观望',
                '观望(偏多)': '观望',
                '观望': '观望',
                '观望(偏空)': '观望',
                '空仓': '观望(偏空)',
                '减仓': '观望',
            }

            if res_ck in ('共振_偏多', '共振_偏空'):
                # 两人一致 → 维持强度
                v_tech = v_kc_base
                rsn_tech = f'KC={v_kc_base}+{res_ck}(维持)'
            else:
                # 分化/混合 → 创业板不同意 → 降档
                v_tech = downgrade.get(v_kc_base, '观望')
                rsn_tech = f'KC={v_kc_base}→{v_tech}+双创{res_ck}(降档)'

            rsn = f"主板:五指数{res}({bulls5}多{bears5}空) 科技:{rsn_tech}"

            oo_sz = vf(row_sz, 'osc_origin'); oo_sh = vf(row_sh, 'osc_origin')

            w.writerow([
                d,
                vf(row_sz, 'close'), vf(row_sh, 'close'), vf(row_cyb, 'close'), vf(row_kc, 'close'),
                vf(row_sz, 'regime'), vf(row_sh, 'regime'), vf(row_cyb, 'regime'), vf(row_kc, 'regime'),
                regime_300.get(d, ''), regime_500.get(d, ''),
                vfs(row_sz, 'chop'), vfs(row_sh, 'chop'), vfs(row_cyb, 'chop'), vfs(row_kc, 'chop'),
                res, sb, sbe, ckr,
                vfi(row_sz, 'bs'), vfi(row_sz, 'ts'), vfi(row_sh, 'bs'), vfi(row_sh, 'ts'),
                vfi(row_cyb, 'bs'), vfi(row_cyb, 'ts'), vfi(row_kc, 'bs'), vfi(row_kc, 'ts'),
                vfi(row_sz, 'bd'), vfi(row_sh, 'bd'), vfi(row_cyb, 'bd'), vfi(row_kc, 'bd'),
                vfi(row_sz, 'bs_ok'), vfi(row_sh, 'bs_ok'), vfi(row_cyb, 'bs_ok'), vfi(row_kc, 'bs_ok'),
                vf(row_sz, 'day_seq'), vf(row_sh, 'day_seq'), vf(row_cyb, 'day_seq'), vf(row_kc, 'day_seq'),
                mw, ww,
                oo_sz, oo_sh,
                v_sz, v_sh, v_cyb, v_kc,
                vf(row_sz, 'reason'), vf(row_sh, 'reason'), vf(row_cyb, 'reason'), vf(row_kc, 'reason'),
                v_main, v_tech, rsn,
            ])

    print(f'\n裁决引擎v7: {out_path}')
    vc_main = Counter(); vc_tech = Counter(); rsc = Counter(); ckr_c = Counter()
    with open(out_path) as f:
        for row in csv.DictReader(f):
            for col, counter in [('verdict_main', vc_main), ('verdict_tech', vc_tech)]:
                v = row[col]
                if '持股' in v and '警戒' not in v: counter['持股类'] += 1
                elif '持股(警戒)' in v: counter['警戒'] += 1
                elif '减仓' in v: counter['减仓'] += 1
                elif '试探' in v: counter['试探类'] += 1
                elif '空仓' in v: counter['空仓'] += 1
                else: counter['观望类'] += 1
            rsc[row['resonance']] += 1
            ckr_c[row['cyb_kc_resonance']] += 1
    total = sum(vc_main.values())
    print(f'总交易日: {total}')
    print(f'\n主板裁决:')
    for k, v in vc_main.most_common(): print(f'  {k}: {v}天 ({v/total*100:.0f}%)')
    print(f'\n科技裁决:')
    for k, v in vc_tech.most_common(): print(f'  {k}: {v}天 ({v/total*100:.0f}%)')
    print(f'\n五指数共振:')
    for k, v in rsc.most_common(): print(f'  {k}: {v}天 ({v/total*100:.0f}%)')
    print(f'\n创业板+科创50共振:')
    for k, v in ckr_c.most_common(): print(f'  {k}: {v}天 ({v/total*100:.0f}%)')


if __name__ == '__main__':
    main()
