#!/usr/bin/env python3
"""
徐小明博客查询工具
==================
分析末尾调用：给定分析日期，抓取徐小明操作策略文章的标题、链接和正文。

日期映射：
  徐小明在 T 日收盘后发布 → 策略针对 T+1（下一个交易日）
  文章标题 = "[周X]操作策略"，周X = 策略目标日的星期几

用法:
  python scripts/blog_monitor.py --date 2026-07-10
  python scripts/blog_monitor.py --date 2026-07-10 --no-content  # 仅标题+链接
"""
import re, requests
from datetime import datetime, timedelta

LIST_URL = "https://blog.sina.com.cn/s/articlelist_1300871220_0_{page}.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
WEEKDAY_MAP = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def fix_enc(text: str) -> str:
    """新浪 latin-1→utf-8 双重编码修复"""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def parse_articles(html: str) -> list[tuple[str, str, str]]:
    """从文章列表页提取 (发布日期, 标题, 链接)，按新→旧排序。"""
    blocks = re.findall(
        r'<span class="atc_title">.*?'
        r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>.*?</span>.*?'
        r'<span class="atc_tm[^"]*">([^<]+)</span>',
        html, re.DOTALL,
    )
    articles = []
    for url, title_raw, date_str in blocks:
        title = fix_enc(title_raw.strip())
        pub_date = date_str.strip()[:10]
        url_full = ("https:" + url) if url.startswith("//") else url
        articles.append((pub_date, title, url_full))
    articles.sort(key=lambda x: x[0], reverse=True)
    return articles


def expected_publish_date(analysis_date: str) -> tuple[str, str]:
    """
    预期发布日期 + 目标标题（基于"下个交易日"修正）。
    徐小明收盘后发布策略，针对下一个交易日。
    周五 → 周末发布的"周一操作策略"；周一至周四 → 前一天发布的策略。
    Returns: (expected_publish_date, target_title)
    """
    dt = datetime.strptime(analysis_date, "%Y-%m-%d")
    w = dt.weekday()
    if w == 4:  # 周五 → 下周一，周日发布
        next_td = dt + timedelta(days=3)
        expected = dt + timedelta(days=2)  # 周日发布
    elif w == 5:  # 周六 → 下周一
        next_td = dt + timedelta(days=2)
        expected = dt + timedelta(days=1)
    elif w == 6:  # 周日 → 下周一（当天发布）
        next_td = dt + timedelta(days=1)
        expected = dt
    else:  # 周一至周四 → 下一个交易日
        next_td = dt + timedelta(days=1)
        expected = dt
    target_title = WEEKDAY_MAP[next_td.weekday()] + "操作策略"
    return expected.strftime("%Y-%m-%d"), target_title


def find_article(analysis_date: str) -> dict | None:
    """
    查找分析日期对应的操作策略文章。
    匹配条件（三重校验）：
    1. 标题 = 下一个交易日的"[周X]操作策略"
    2. 发布日期窗口
    3. 发布日期不能旧于预期
    """
    dt = datetime.strptime(analysis_date, "%Y-%m-%d")
    expected, target_title = expected_publish_date(analysis_date)

    for page in range(1, 5):
        try:
            resp = requests.get(
                LIST_URL.format(page=page), headers=HEADERS, timeout=15
            )
            resp.encoding = "utf-8"
        except Exception:
            break

        articles = parse_articles(resp.text)
        if not articles:
            break

        for pub_date, title, url in articles:
            if target_title not in title:
                continue
            # 周五的分析日→文章在周末发布（pub_date >= analysis_date 正常）
            dt = datetime.strptime(analysis_date, "%Y-%m-%d")
            if dt.weekday() != 4 and pub_date > analysis_date:
                continue
            if pub_date < expected:
                continue  # 太旧，跳过（如上周的同名文章）
            return {
                "title": title,
                "url": url,
                "publish_date": pub_date,
                "target_date": analysis_date,
            }

        if len(articles) < 30:
            break

    return None


def fetch_content(article_url: str) -> str:
    """
    抓取博文正文。
    正文位于 <div class="articalContent"> 内的 <font> 标签中。
    """
    try:
        resp = requests.get(article_url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
    except Exception:
        return ""

    html = resp.text

    # 找正文区起点
    start = html.find('class="articalContent')
    if start == -1:
        return ""

    chunk = html[start:]

    # 提取所有 <font> 块内的文本
    fonts = re.findall(
        r'<font[^>]*>(.*?)</FONT>', chunk, re.DOTALL | re.IGNORECASE
    )
    lines = []
    for f in fonts:
        # 清理 HTML 残留
        f = re.sub(r'<a[^>]*>|</a>|<wbr/?>', '', f, flags=re.IGNORECASE)
        f = f.replace("&nbsp;", " ")
        f = re.sub(r'<br\s*/?>', '\n', f)
        f = re.sub(r'<[^>]+>', '', f)
        f = f.strip()
        if f:
            lines.append(f)

    return "\n\n".join(lines)


def main():
    import argparse

    p = argparse.ArgumentParser(description="徐小明博客查询")
    p.add_argument("--date", required=True, help="分析日期 YYYY-MM-DD")
    p.add_argument(
        "--no-content", action="store_true", help="仅输出标题+链接，不抓正文"
    )
    args = p.parse_args()

    article = find_article(args.date)
    if not article:
        print("无对应操作策略文章")
        return

    print(f"TITLE: {article['title']}")
    print(f"URL: {article['url']}")
    print(f"PUBLISH: {article['publish_date']}")
    print(f"TARGET: {article['target_date']}")

    if not args.no_content:
        content = fetch_content(article["url"])
        if content:
            print("\n---BEGIN CONTENT---")
            print(content)
            print("---END CONTENT---")
        else:
            print("\n[正文提取失败]")


if __name__ == "__main__":
    main()
