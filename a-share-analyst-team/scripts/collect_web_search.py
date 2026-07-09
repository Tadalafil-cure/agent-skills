#!/usr/bin/env python3
"""
A-share-analyst-team · 网络搜索采集器 (F#11) — v3.0

双引擎（Firecrawl 主力 + Baidu 补中文）· 3 轮流水线 · 30s 间隔 · 边抽边搜

用法:
    python3 collect_web_search.py --symbol 002709 --name 天赐材料 --industry 电解液 --output /tmp/xxx/data/web_search_data.json
"""

import argparse, json, os, sys, time, re, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from urllib.parse import urlparse, quote as url_quote
from datetime import datetime
from typing import Optional


# ── 配置 ──
MAX_RESULTS_PER_QUERY = 10
MAX_WORKERS = 4           # 抓取并发
ROUND_INTERVAL = 30        # 轮间间隔（秒，含搜索耗时）
SEARCH_TIMEOUT = 25        # 单次搜索超时
SCRAPING_TIMEOUT = 20
SEARXNG_URL = "http://127.0.0.1:8880"
SKIP_DOMAINS = {"mp.weixin.qq.com"}


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", 124


# ═══════════════════════════════════════════════════════════════
#  SearXNG 保活
# ═══════════════════════════════════════════════════════════════

def _check_searxng():
    """确保 SearXNG 可用。假死检测 + 自动重启。"""
    import urllib.request as ur
    config_ok = False
    try:
        ur.urlopen(f"{SEARXNG_URL}/config", timeout=3)
        config_ok = True
    except:
        pass

    search_ok = False
    if config_ok:
        try:
            resp = ur.urlopen(f"{SEARXNG_URL}/search?q=test&engines=baidu&format=json", timeout=10)
            d = json.loads(resp.read())
            search_ok = len(d.get("results", [])) > 0
        except:
            pass

    if config_ok and not search_ok:
        print("[SearXNG] 假死——重启...", file=sys.stderr)
        config_ok = False

    if not config_ok:
        subprocess.Popen(
            ["python3", "-m", "searx.webapp"],
            cwd="/home/admin/searxng",
            env={
                "SEARXNG_SETTINGS_PATH": "/home/admin/.searxng/settings.yml",
                "PATH": "/usr/bin:/usr/local/bin"
            },
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(8)
        try:
            resp = ur.urlopen(
                f"{SEARXNG_URL}/search?q=test&engines=baidu&format=json", timeout=10
            )
            d = json.loads(resp.read())
            n = len(d.get("results", []))
            if n > 0:
                print(f"[SearXNG] 已启动 ({n} results)", file=sys.stderr)
            else:
                print("[SearXNG] 启动后 0 results——可能 CAPTCHA", file=sys.stderr)
        except Exception as e:
            print(f"[SearXNG] 启动失败: {e}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
#  搜索后端：Firecrawl（主力）+ Baidu（补中文）
# ═══════════════════════════════════════════════════════════════

def _search_firecrawl(query: str, max_results: int = 10) -> list[dict]:
    """Firecrawl keyless 搜索。返回 [{\"title\",\"href\",\"body\"}]。"""
    try:
        from firecrawl.v2.client import FirecrawlClient
        client = FirecrawlClient()
        result = client.search(query)
        items = []
        for r in result.web[:max_results]:
            items.append({
                "title": r.title or "",
                "href": r.url or "",
                "body": r.description or "",
                "_source": "firecrawl",
            })
        return items
    except Exception as e:
        print(f"  [firecrawl] {type(e).__name__}: {e}", file=sys.stderr)
        return []


def _search_baidu(query: str, max_results: int = 10) -> list[dict]:
    """SearXNG + Baidu JSON API 搜索。返回 [{\"title\",\"href\",\"body\"}]。"""
    import urllib.request as ur
    # 文件锁限频（≥20s）
    lock_dir = Path(os.environ.get("TASK_BASE", "/tmp")) / "data"
    lock_file = lock_dir / ".ddgs_lock"
    lock_dir.mkdir(parents=True, exist_ok=True)

    if lock_file.exists():
        try:
            elapsed = time.time() - float(lock_file.read_text().strip())
            if elapsed < 20:
                wait = 20 - elapsed
                print(f"  [baidu] 限频等待 {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
        except:
            pass

    try:
        q = url_quote(query)
        url = f"{SEARXNG_URL}/search?q={q}&engines=baidu&format=json"
        req = ur.Request(url)
        resp = ur.urlopen(req, timeout=SEARCH_TIMEOUT)
        raw = json.loads(resp.read().decode())
        lock_file.write_text(str(time.time()))

        items = []
        for r in raw.get("results", [])[:max_results]:
            items.append({
                "title": r.get("title", ""),
                "href": r.get("url", ""),
                "body": r.get("content", ""),
                "_source": "baidu",
            })
        return items
    except Exception as e:
        lock_file.write_text(str(time.time()))
        print(f"  [baidu] {type(e).__name__}: {e}", file=sys.stderr)
        return []


def _search_dual(query_fc: str, query_bd: str, max_results: int = 10) -> list[dict]:
    """双引擎并行搜索 → 合并去重（Firecrawl 优先保留）。"""
    results: list[dict] = []
    seen: set[str] = set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fc_fut: Future = pool.submit(_search_firecrawl, query_fc, max_results)
        bd_fut: Future = pool.submit(_search_baidu, query_bd, max_results)

        # Firecrawl 先到先入（主力优先）
        for fut, label in [(fc_fut, "firecrawl"), (bd_fut, "baidu")]:
            try:
                items = fut.result(timeout=SEARCH_TIMEOUT + 5)
                n_added = 0
                for r in items:
                    href = r.get("href", "")
                    if href and href not in seen:
                        seen.add(href)
                        results.append(r)
                        n_added += 1
                print(f"  [{label}] {len(items)} 条 → {n_added} 新增", file=sys.stderr)
            except Exception as e:
                print(f"  [{label}] 失败: {e}", file=sys.stderr)

    return results[:max_results]


# ═══════════════════════════════════════════════════════════════
#  分层抓取：urllib → scrapling get → scrapling fetch
# ═══════════════════════════════════════════════════════════════

def _urllib_fetch(url: str) -> Optional[str]:
    """第 1 层：urllib 直抓。"""
    import urllib.request as ur
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        req = ur.Request(url, headers=headers)
        resp = ur.urlopen(req, timeout=SCRAPING_TIMEOUT)
        html = resp.read().decode("utf-8", errors="replace")
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'&nbsp;|&ensp;|&emsp;', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean if len(clean) > 300 else None
    except:
        return None


def _scraping_get(url, out_path):
    _, code = run(f"scrapling extract get '{url}' {out_path}", timeout=SCRAPING_TIMEOUT)
    return code == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 50


def _scraping_fetch(url, out_path):
    _, code = run(
        f"scrapling extract fetch '{url}' {out_path} --disable-resources --network-idle",
        timeout=SCRAPING_TIMEOUT + 10
    )
    return code == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 50


def _is_junk(text):
    junk = ["Enable JavaScript", "cookies to continue", "Please enable JS",
            "请启用JavaScript", "403 Forbidden", "Access Denied"]
    t = text[:500].lower()
    return any(j.lower() in t for j in junk)


def _extract_keyword_summary(text):
    """从文本提取业务关键词相关摘要。"""
    keywords = ["业务", "产品", "客户", "技术", "产能", "合作", "研发",
                "行业", "市场", "政策", "趋势", "竞争", "份额", "专利",
                "突破", "进展", "公告", "项目", "战略",
                "electrolyte", "production", "capacity", "market",
                "revenue", "lithium", "battery", "LiFSI", "factory"]
    skip_prefix = ["skip to", "navigation", "sidebar", "footer", "登录", "注册",
                   "首页", "搜索", "var ", "function(", "window.", "document.",
                   "img src", "logo", "立即下载", "扫码"]
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        if len(s) < 25:
            continue
        if any(w.lower() in s[:30].lower() for w in skip_prefix):
            continue
        if any(kw.lower() in s.lower() for kw in keywords):
            lines.append(s[:200])
        if len(lines) >= 3:
            break
    return " | ".join(lines) if lines else text[:200]


def extract_url_content(url, idx, tmpdir):
    """分层抓取：urllib → scrapling_get → scrapling_fetch"""
    domain = urlparse(url).netloc.lower()
    if domain in SKIP_DOMAINS:
        return "skipped", ""

    # L1: urllib
    text = _urllib_fetch(url)
    if text and not _is_junk(text):
        summary = _extract_keyword_summary(text)
        if summary:
            return "urllib", summary

    # L2: scrapling get
    fname = f"{idx:02d}_{domain.replace('.','_')}.md"
    out_md = Path(tmpdir) / fname
    if _scraping_get(url, str(out_md)):
        summary = _extract_keyword_summary(Path(out_md).read_text("utf-8", errors="replace"))
        if summary and not _is_junk(summary):
            return "scrapling_get", summary

    # L3: scrapling fetch
    if _scraping_fetch(url, str(out_md)):
        summary = _extract_keyword_summary(Path(out_md).read_text("utf-8", errors="replace"))
        if summary and not _is_junk(summary):
            return "scrapling_fetch", summary

    return "failed", ""


# ═══════════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="A-team 网络搜索采集器 v3.0 (Firecrawl + Baidu)")
    parser.add_argument("--symbol", required=True, help="股票代码")
    parser.add_argument("--name", required=True, help="股票简称")
    parser.add_argument("--industry", required=True, help="所属行业")
    parser.add_argument("--output", required=True, help="输出 JSON 路径")
    args = parser.parse_args()

    tmpdir = Path(args.output).parent / "web_search_tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)

    print(f"[F#11] {args.name}({args.symbol}) · {args.industry}", file=sys.stderr)
    print(f"[F#11] 双引擎: Firecrawl (主力) + Baidu (补中文) · 3 轮流水线 · ≥30s/轮", file=sys.stderr)

    # 保活
    _check_searxng()

    # ── 3 轮搜索：给所有 Agent 一张共同地图 ──
    rounds = [
        {
            "label": "R1·个股概况",
            "fc": f"{args.name} {args.symbol} business overview products main business",
            "bd": f"{args.name} {args.symbol} 主营 业务 产品",
        },
        {
            "label": "R2·行业全貌",
            "fc": f"{args.industry} industry landscape supply chain competition market size",
            "bd": f"{args.industry} 行业 产业链 竞争格局 市场规模",
        },
        {
            "label": "R3·多空观点",
            "fc": f"{args.name} {args.symbol} analyst view bull bear rating target price",
            "bd": f"{args.name} 研报 评级 看多 看空 目标价",
        },
    ]

    extraction_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    all_items: list[dict] = []
    all_futures: list[Future] = []
    seen_urls: set[str] = set()
    item_idx = 0

    for ri, rd in enumerate(rounds):
        t0 = time.time()
        print(f"\n── {rd['label']} ──", file=sys.stderr)

        # Phase A: 双引擎并行搜索
        search_results = _search_dual(rd["fc"], rd["bd"], MAX_RESULTS_PER_QUERY)
        new_urls = 0
        for r in search_results:
            href = r.get("href", "")
            if href and href not in seen_urls:
                seen_urls.add(href)
                item_idx += 1
                all_items.append({
                    "idx": item_idx,
                    "title": r.get("title", ""),
                    "url": href,
                    "snippet": r.get("body", "")[:200],
                    "source": r.get("_source", "?"),
                    "round": ri + 1,
                })
                new_urls += 1
        print(f"  → {new_urls} 新 URL（共 {len(all_items)}）", file=sys.stderr)

        # Phase B: 启动抓取（后台线程，不等待）
        for item in all_items:
            if "method" not in item:  # 未抓取过
                url = item["url"]
                fut = extraction_pool.submit(extract_url_content, url, item["idx"], tmpdir)
                all_futures.append((fut, item))

        # Phase C: 等待到 30s 标记（含搜索耗时），边等边抽
        elapsed = time.time() - t0
        if ri < len(rounds) - 1:
            wait = max(0, ROUND_INTERVAL - elapsed)
            if wait > 0:
                print(f"  ⏳ 等待 {wait:.0f}s（本轮 {elapsed:.0f}s）...", file=sys.stderr)
                time.sleep(wait)

    # ── 收集所有抓取结果 ──
    print(f"\n── 收集抓取结果（{len(all_futures)} 个任务）──", file=sys.stderr)
    for fut, item in all_futures:
        try:
            method, summary = fut.result(timeout=30)
        except Exception as e:
            method, summary = "failed", str(e)
        item["method"] = method
        item["summary"] = summary[:500] if summary else ""

    # 补漏：未抓取的标为 skipped
    for item in all_items:
        if "method" not in item:
            item["method"] = "skipped"
            item["summary"] = ""

    # ── 分类：R1+R3→个股，R2→行业（共同地图，各有侧重）──
    stock_items = [i for i in all_items if i["round"] in (1, 3)]
    industry_items = [i for i in all_items if i["round"] == 2]

    output = {
        "meta": {
            "symbol": args.symbol,
            "name": args.name,
            "industry": args.industry,
            "generated_at": datetime.now().isoformat(),
            "source": "Firecrawl (keyless) + SearXNG/Baidu + urllib | scrapling",
            "version": "3.0",
            "rounds": 3,
            "round_interval_s": ROUND_INTERVAL,
            "note": "R1·个股概况 + R3·多空观点 → stock_news | R2·行业全貌 → industry_news。各 Agent 以此地图为基线，按需自搜深挖。",
        },
        "stock_news": {
            "queries": [f"{r['fc']} ∥ {r['bd']}" for r in rounds],
            "label": "个股动态（3轮深挖）",
            "total_scraped": sum(1 for i in stock_items if i.get("method") not in ("failed", "skipped", None)),
            "total_failed": sum(1 for i in stock_items if i.get("method") == "failed"),
            "results": sorted(stock_items, key=lambda x: x["idx"])[:MAX_RESULTS_PER_QUERY],
        },
        "industry_news": {
            "queries": [f"{rounds[1]['fc']} ∥ {rounds[1]['bd']}"],
            "label": "行业全貌（R2·行业全貌）",
            "total_scraped": sum(1 for i in industry_items if i.get("method") not in ("failed", "skipped", None)),
            "total_failed": sum(1 for i in industry_items if i.get("method") == "failed"),
            "results": sorted(industry_items, key=lambda x: x["idx"])[:MAX_RESULTS_PER_QUERY],
        },
    }

    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    extraction_pool.shutdown(wait=False)

    n_stock = output["stock_news"]["total_scraped"]
    n_ind = output["industry_news"]["total_scraped"]
    print(f"\n[F#11] 完成 → {args.output}", file=sys.stderr)
    print(f"  个股: {n_stock}/{len(stock_items)} 条 · 行业: {n_ind}/{len(industry_items)} 条", file=sys.stderr)
    src_counts = {}
    for i in all_items:
        s = i.get("source", "?")
        src_counts[s] = src_counts.get(s, 0) + 1
    print(f"  来源: {src_counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
