#!/usr/bin/env python3
"""
封板测试 · 全量历史实测
========================
每年抽取50篇操作策略文章，提取徐小明方向判断，与v7裁决引擎比对。

方法：正则提取（参考v13/v16盲测方法）+ 方向合并比对
  - 模型空仓+观望 = "非看多"
  - 模型持股+试探+减仓 = "看多"
  - 徐小明：从文章中提取操作方向（买/持股/减仓/卖/空仓/观望/等）
  - 只在这两级之间反转才算方向矛盾
"""
import csv, re, os, random, sys
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# ============================================================
# 1. 文章解析
# ============================================================

def parse_articles(year_file: str) -> list:
    """解析年卷文件，返回文章列表 [{date, title, type, content}]"""
    with open(year_file, encoding='utf-8') as f:
        content = f.read()

    parts = content.split('\n---\n')
    articles = []

    for part in parts[1:]:  # skip header
        part = part.strip()
        if not part or len(part) < 50:
            continue

        lines = part.split('\n')
        # Extract title from first heading
        title = ''
        date_str = ''
        article_type = 'other'

        for line in lines:
            line = line.strip()
            # Date line: > 徐小明 · 投资明见 · 2026-01-04 12:45
            m = re.search(r'(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}', line)
            if m:
                date_str = m.group(1)
            # Title
            if line.startswith('# '):
                title = line[2:].strip()
                if '操作策略' in title:
                    article_type = 'strategy'
                elif '午评' in title or '午间' in title:
                    article_type = 'noon'
                elif '周一' in title or '周二' in title or '周三' in title or '周四' in title or '周五' in title:
                    if '操作策略' in title:
                        article_type = 'strategy'

        if date_str and title:
            articles.append({
                'date': date_str,
                'title': title,
                'type': article_type,
                'content': part
            })

    return articles


# ============================================================
# 2. 方向提取（正则）
# ============================================================

def extract_direction(article: dict) -> dict:
    """
    从文章中提取徐小明的操作方向。
    返回 {direction: '看多'/'看空'/'中性'/'不重要', confidence: 'high'/'medium'/'low'}
    """
    content = article['content']
    title = article['title']

    # 关键词计数
    bullish_patterns = [
        (r'满仓|持股|买入|抄底|建仓|加仓', 3),
        (r'趋势突破|趋势之上|突破趋势', 2),
        (r'战略性看多|底部区域|大底', 2),
        (r'试探|试多|小仓位', 1),
        (r'偏多|看涨|乐观', 1),
    ]
    bearish_patterns = [
        (r'空仓|清仓|减仓|卖出|离场', 3),
        (r'趋势破位|破位趋势|跌破趋势', 2),
        (r'减仓防守|防守', 2),
        (r'偏空|看跌|不乐观', 1),
    ]
    neutral_patterns = [
        (r'观望|多看少动|随缘|等|耐心', 2),
        (r'不重要|没有操作|无信号', 2),
        (r'没有结构|没有序列|没有趋势', 1),
    ]

    bull_score = 0
    for pat, weight in bullish_patterns:
        if re.search(pat, content):
            bull_score += weight

    bear_score = 0
    for pat, weight in bearish_patterns:
        if re.search(pat, content):
            bear_score += weight

    neutral_score = 0
    for pat, weight in neutral_patterns:
        if re.search(pat, content):
            neutral_score += weight

    # 决策
    if bull_score == 0 and bear_score == 0 and neutral_score == 0:
        return {'direction': '无法判断', 'confidence': 'low'}

    if bull_score > bear_score + 3 and bull_score > neutral_score:
        return {'direction': '看多', 'confidence': 'high' if bull_score >= 5 else 'medium'}
    elif bear_score > bull_score + 3 and bear_score > neutral_score:
        return {'direction': '看空', 'confidence': 'high' if bear_score >= 5 else 'medium'}
    elif neutral_score > bull_score and neutral_score > bear_score:
        return {'direction': '中性', 'confidence': 'medium'}
    elif bull_score > 0 and bear_score == 0:
        return {'direction': '偏多', 'confidence': 'low'}
    elif bear_score > 0 and bull_score == 0:
        return {'direction': '偏空', 'confidence': 'low'}
    else:
        return {'direction': '混合', 'confidence': 'low'}


# ============================================================
# 3. 抽样
# ============================================================

def sample_articles(articles: list, n: int = 50, seed: int = 42) -> list:
    """从文章列表中抽取n篇，优先操作策略文章，确保月度覆盖"""
    random.seed(seed)

    # 分开策略和非策略
    strategy = [a for a in articles if a['type'] == 'strategy']
    others = [a for a in articles if a['type'] != 'strategy']

    # 确保月度分布
    by_month = defaultdict(list)
    for a in strategy:
        m = a['date'][:7]
        by_month[m].append(a)

    # 每个月至少1-2篇
    sampled = []
    months = sorted(by_month.keys())
    per_month_base = max(1, n // len(months))

    for m in months:
        pool = by_month[m]
        if len(pool) <= per_month_base:
            sampled.extend(pool)
        else:
            sampled.extend(random.sample(pool, per_month_base))

    # 如果不够n，从策略池随机补
    if len(sampled) < n:
        remaining = [a for a in strategy if a not in sampled]
        if remaining:
            extra = random.sample(remaining, min(n - len(sampled), len(remaining)))
            sampled.extend(extra)

    # 如果还不够，从非策略补
    if len(sampled) < n and others:
        extra = random.sample(others, min(n - len(sampled), len(others)))
        sampled.extend(extra)

    # 去重并按日期排序
    seen = set()
    unique = []
    for a in sorted(sampled, key=lambda x: x['date']):
        if a['date'] not in seen:
            seen.add(a['date'])
            unique.append(a)

    return unique[:n]


# ============================================================
# 4. 比对
# ============================================================

def model_direction(verdict: str) -> str:
    """模型裁决 → 方向"""
    v = verdict.strip()
    if '持股' in v and '警戒' not in v:
        return '看多'
    if '减仓' in v:
        return '看多'  # 减仓是有仓位→看多偏防御
    if '试探' in v:
        return '看多'
    if '空仓' in v:
        return '非看多'
    if '观望' in v:
        return '非看多'
    return '非看多'


def xxm_direction(d: str) -> str:
    """徐小明方向 → 统一分类"""
    if d in ('看多', '偏多'):
        return '看多'
    if d in ('看空', '偏空'):
        return '非看多'
    if d in ('中性', '混合', '无法判断'):
        return '非看多'
    return '非看多'


def compare(model_dir: str, xxm_dir: str) -> str:
    """比对两个方向"""
    if model_dir == xxm_dir:
        return '一致'
    if model_dir == '看多' and xxm_dir == '非看多':
        return '模型偏多'
    if model_dir == '非看多' and xxm_dir == '看多':
        return '模型偏空'
    return '一致'


# ============================================================
# 5. 主流程
# ============================================================

def main():
    print("=" * 70)
    print("封板测试 · 全量历史实测")
    print("=" * 70)

    # 加载模型裁决
    print("\n[1/5] 加载模型裁决...")
    verdicts = {}
    with open(BASE / 'data/verdict_v7.csv', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            verdicts[row['date']] = row
    print(f"  裁决天数: {len(verdicts)}")

    # 解析所有文章
    print("\n[2/5] 解析文章...")
    article_dir = BASE / 'references/original-articles'
    all_articles = {}
    for year_file in sorted(article_dir.glob('year-*.md')):
        year = year_file.stem.replace('year-', '')
        articles = parse_articles(str(year_file))
        all_articles[year] = articles
        print(f"  {year}: {len(articles)} 篇")

    # 逐年抽样+比对
    print("\n[3/5] 抽样+比对...")
    yearly_results = {}

    for year in sorted(all_articles.keys()):
        articles = all_articles[year]
        sampled = sample_articles(articles, 50, seed=int(year))

        results = []
        for a in sampled:
            d = a['date']
            # 找最近交易日的模型裁决
            model_v = None
            for offset in range(5):
                check_date = d
                if check_date in verdicts:
                    model_v = verdicts[check_date]['verdict_final']
                    break
                # try previous trading day
                dt = datetime.strptime(d, '%Y-%m-%d') - timedelta(days=offset+1)
                check_date = dt.strftime('%Y-%m-%d')
                if check_date in verdicts:
                    model_v = verdicts[check_date]['verdict_final']
                    break

            if model_v is None:
                continue

            # 提取徐小明方向
            xxm = extract_direction(a)
            m_dir = model_direction(model_v)
            x_dir = xxm_direction(xxm['direction'])
            cmp = compare(m_dir, x_dir)

            results.append({
                'date': d,
                'title': a['title'][:40],
                'type': a['type'],
                'model_verdict': model_v,
                'xxm_direction': xxm['direction'],
                'xxm_confidence': xxm['confidence'],
                'model_dir': m_dir,
                'xxm_dir': x_dir,
                'comparison': cmp,
            })

        yearly_results[year] = results

        # 统计
        total = len(results)
        agree = sum(1 for r in results if r['comparison'] == '一致')
        model_bull = sum(1 for r in results if r['comparison'] == '模型偏多')
        model_bear = sum(1 for r in results if r['comparison'] == '模型偏空')
        rate = agree / total * 100 if total else 0

        print(f"\n  {year}: {total}篇, 一致={agree}({rate:.0f}%), 模型偏多={model_bull}, 模型偏空={model_bear}")

        yearly_results[year + '_stats'] = {
            'total': total, 'agree': agree, 'model_bull': model_bull,
            'model_bear': model_bear, 'rate': rate
        }

    # 汇总
    print(f"\n[4/5] 全量汇总...")
    all_agree = sum(yearly_results[y+'_stats']['agree'] for y in sorted(all_articles.keys()))
    all_total = sum(yearly_results[y+'_stats']['total'] for y in sorted(all_articles.keys()))
    overall_rate = all_agree / all_total * 100 if all_total else 0

    print(f"\n{'='*70}")
    print(f"封板测试结果")
    print(f"{'='*70}")
    print(f"总样本: {all_total} 篇 (7年 × ~50篇/年)")
    print(f"总一致: {all_agree} 篇 ({overall_rate:.1f}%)")
    print(f"\n年度分解:")
    for year in sorted(all_articles.keys()):
        s = yearly_results[year+'_stats']
        bar = '█' * int(s['rate']/5) + '░' * (20 - int(s['rate']/5))
        print(f"  {year}: {s['agree']:>3}/{s['total']:<3} {s['rate']:5.1f}% {bar} "
              f"偏多={s['model_bull']} 偏空={s['model_bear']}")

    # 不一致案例分析
    print(f"\n[5/5] 方向矛盾案例...")
    conflicts = []
    for year in sorted(all_articles.keys()):
        for r in yearly_results[year]:
            if r['comparison'] in ('模型偏多', '模型偏空'):
                conflicts.append(r)

    # 按类型分组
    by_type = defaultdict(list)
    for c in conflicts:
        by_type[c['comparison']].append(c)

    for cmp_type, items in sorted(by_type.items()):
        print(f"\n  {cmp_type} ({len(items)}次):")
        for item in items[:5]:
            print(f"    {item['date']} | 模型={item['model_verdict']:>12} | "
                  f"徐小明={item['xxm_direction']:>6} ({item['xxm_confidence']}) | "
                  f"{item['title']}")

    # 写 JSON
    output_path = BASE / 'data/seal_test_results.json'
    import json
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({k: v for k, v in yearly_results.items() if not k.endswith('_stats')},
                  f, ensure_ascii=False, indent=2, default=str)
    print(f"\n详细结果: {output_path}")

    # 输出 README 摘要
    print(f"\n{'='*70}")
    print("README 摘要 (粘贴到 README.md):")
    print(f"{'='*70}")
    print(f"""
## 封板测试 (v4.4.3 · {datetime.now().strftime('%Y-%m-%d')})

全量历史实测：7年共 {all_total} 篇操作策略文章，正则提取徐小明方向判断，与v7裁决引擎比对。

| 年份 | 样本 | 一致 | 一致率 | 模型偏多 | 模型偏空 |
|------|:--:|:--:|:--:|:--:|:--:|""")

    for year in sorted(all_articles.keys()):
        s = yearly_results[year+'_stats']
        print(f"| {year} | {s['total']} | {s['agree']} | {s['rate']:.0f}% | {s['model_bull']} | {s['model_bear']} |")

    print(f"""
**总一致率: {overall_rate:.1f}%** ({all_agree}/{all_total})

方向矛盾共 {len(conflicts)} 次 ({len(conflicts)/all_total*100:.1f}%)，其中：
- 模型偏多（模型看多、徐小明非看多）: {len(by_type.get('模型偏多',[]))}次
- 模型偏空（模型非看多、徐小明看多）: {len(by_type.get('模型偏空',[]))}次

> 注：正则提取为近似方法（参考v13盲测，正则vs LLM约差10-15%）。方向矛盾的真实率在LLM提取下预期更低（<5%，参考v16结论）。""")


if __name__ == '__main__':
    random.seed(42)
    main()
