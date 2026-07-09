"""
stats.gov.cn 月度数据爬取器
依赖 Playwright (URL发现) + urllib (页面解析)
"""
import re
import json
import ssl
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MacroDataMiddleware/1.0)"}

URL_INDEX_PATH = Path(__file__).parent / "url_index.json"


def _http_get(url: str, timeout: int = 15) -> str:
    try:
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)
        return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_number(html: str, patterns: List[str]) -> Optional[float]:
    """从 HTML 文本中按正则模式提取第一个数值"""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&ensp;|&emsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return float(m.group(1))
    return None


def _extract_date_from_title(title: str) -> Optional[str]:
    """从标题提取数据月份，如 '2026年5月份' → '2026-05'"""
    # 单月
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", title)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    # 1-X月累计 → 取截至月份
    m = re.search(r"(\d{4})\s*年\s*1\s*[—\-]\s*(\d{1,2})\s*月", title)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    # 季度
    m = re.search(r"(\d{4})\s*年\s*[一二三四]\s*季度", title)
    if m:
        quarter_map = {"一": "03", "二": "06", "三": "09", "四": "12"}
        q = re.search(r"[一二三四]", title[m.start():m.end()])
        if q:
            return f"{m.group(1)}-{quarter_map[q.group()]}"
    return None


# ── 各指标提取正则 ──

EXTRACTORS = {
    "CPI": {
        "patterns": [
            r"全国居民消费价格(?:同比)?\s*(?:上涨|下降)\s*(-?\d+\.?\d*)\s*%",
        ],
        "unit": "%",
        "indicator": "CPI同比",
    },
    "PPI": {
        "patterns": [
            r"工业生产者出厂价格(?:同比)?\s*(?:上涨|下降|降幅)\s*(-?\d+\.?\d*)\s*%",
        ],
        "unit": "%",
        "indicator": "PPI同比",
        # PPI 特殊处理: "降幅收窄" → 负值
        "post_process": lambda v, text: (
            -v if re.search(r"(?:下降|降幅|降)", text[:200]) and v > 0 else v
        ),
    },
    "PMI": {
        "patterns": [
            r"制造业(?:采购经理指数|PMI)[^0-9]*?(\d+\.?\d*)\s*%",
        ],
        "unit": "指数",
        "indicator": "制造业PMI",
    },
    "工业增加值": {
        "patterns": [
            r"规模以上工业增加值.*?增[长長]\s*(-?\d+\.?\d*)\s*%",
        ],
        "unit": "%",
        "indicator": "工业增加值同比",
    },
    "社零": {
        "patterns": [
            r"社会消费品零售总额.*?增[长長]\s*(-?\d+\.?\d*)\s*%",
        ],
        "unit": "%",
        "indicator": "社零同比",
    },
    "固投": {
        "patterns": [
            r"(?:全国)?固定资产投资.*?(?:同比)?增[长長]\s*(-?\d+\.?\d*)\s*%",
        ],
        "unit": "%",
        "indicator": "固投同比(累计)",
    },
}


def load_url_index() -> Dict[str, List[dict]]:
    """加载 URL 索引"""
    if URL_INDEX_PATH.exists():
        with open(URL_INDEX_PATH) as f:
            return json.load(f)
    return {}


def scrape_indicator(category: str, max_pages: int = 8) -> pd.DataFrame:
    """
    从 URL 索引中取 category 对应的发布页，逐页提取数值。
    返回标准化 DataFrame。
    """
    url_index = load_url_index()
    if category not in url_index or category not in EXTRACTORS:
        return pd.DataFrame(columns=["date", "indicator", "value", "unit", "source"])

    config = EXTRACTORS[category]
    items = url_index[category][:max_pages]
    rows = []

    for item in items:
        html = _http_get(item["url"])
        if not html:
            continue
        
        val = _extract_number(html, config["patterns"])
        if val is None:
            continue

        # 后处理 (如 PPI 符号修正)
        if "post_process" in config:
            val = config["post_process"](val, html)

        data_date = _extract_date_from_title(item["text"])
        if data_date is None:
            data_date = f"{item['release_date'][:4]}-{item['release_date'][4:6]}"

        rows.append({
            "date": pd.Timestamp(data_date),
            "indicator": config["indicator"],
            "value": val,
            "unit": config["unit"],
            "source": f"stats.gov.cn/{item['release_date']}",
        })

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.sort_values("date").drop_duplicates(subset=["date", "indicator"]).reset_index(drop=True)
    return df


def update_url_index(max_pages: int = 20) -> Dict[str, List[dict]]:
    """
    用 Playwright 渲染 stats.gov.cn 索引页，更新 URL 索引。
    覆盖最近 max_pages 页。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠️ Playwright 未安装，跳过 URL 索引更新")
        return load_url_index()

    indicator_keywords = {cat: cfg.get("keywords", [cat]) for cat, cfg in EXTRACTORS.items()}
    # 补充关键词
    indicator_keywords["CPI"] = ["居民消费价格", "CPI"]
    indicator_keywords["PPI"] = ["工业生产者出厂价格", "PPI"]
    indicator_keywords["PMI"] = ["采购经理指数", "PMI"]
    indicator_keywords["工业增加值"] = ["规模以上工业增加值增长"]
    indicator_keywords["社零"] = ["社会消费品零售总额"]
    indicator_keywords["固投"] = ["固定资产投资"]

    all_links = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        urls = ["https://www.stats.gov.cn/sj/zxfb/"]
        for i in range(1, max_pages):
            urls.append(f"https://www.stats.gov.cn/sj/zxfb/index_{i}.html")

        for idx, url in enumerate(urls):
            try:
                page = browser.new_page()
                page.goto(url, timeout=20000, wait_until="networkidle")
                links = page.evaluate('''() => {
                    const as = document.querySelectorAll('a[href]');
                    return Array.from(as).map(a => ({
                        href: a.href,
                        text: a.textContent.trim()
                    }));
                }''')
                for l in links:
                    href = l["href"]
                    text = l["text"]
                    m = re.search(r"/sj/zxfb(?:hjd)?/(\d{6})/t(\d{8})_(\d+)\.html", href)
                    if not m:
                        continue
                    for cat, kws in indicator_keywords.items():
                        if any(kw in text for kw in kws):
                            if cat not in all_links:
                                all_links[cat] = []
                            all_links[cat].append({
                                "release_date": m.group(2),
                                "text": text[:100],
                                "url": href,
                            })
                            break
                page.close()
            except Exception as e:
                print(f"  [{idx+1}] {url[-20:]}: {e}")
        browser.close()

    # 去重
    for cat in all_links:
        seen = set()
        unique = []
        for item in sorted(all_links[cat], key=lambda x: x["release_date"], reverse=True):
            if item["url"] not in seen:
                seen.add(item["url"])
                unique.append(item)
        all_links[cat] = unique

    with open(URL_INDEX_PATH, "w") as f:
        json.dump(all_links, f, ensure_ascii=False, indent=2)

    print(f"URL 索引已更新: {sum(len(v) for v in all_links.values())} 条链接")
    return all_links


# ── CLI ──
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        update_url_index(max_pages=20)
    else:
        for cat in ["CPI", "PPI", "PMI", "工业增加值", "社零", "固投"]:
            df = scrape_indicator(cat)
            if len(df) > 0:
                print(f"\n=== {cat} ({len(df)}条) ===")
                print(df.to_string())
            else:
                print(f"\n=== {cat}: 无数据 ===")
