#!/usr/bin/env python3
"""
SearXNG/Baidu + Firecrawl 安全搜索封装 —— 文件锁限频，子 Agent 自搜用

v3.0: 双引擎（Firecrawl 主力 + Baidu 补中文），同名兼容

用法:
    python3 ddgs_safe.py -q "搜索词" -m 6
    python3 ddgs_safe.py -q "搜索词" -m 6 --json
"""

import argparse, json, os, sys, time
from pathlib import Path
from urllib.parse import quote as url_quote
from concurrent.futures import ThreadPoolExecutor, as_completed

MIN_INTERVAL = 20
SEARXNG_URL = "http://127.0.0.1:8880"
SEARCH_TIMEOUT = 25


def get_lock_path():
    task_base = os.environ.get("TASK_BASE", "/tmp")
    return Path(task_base) / "data" / ".ddgs_lock"


def wait_if_needed(lock_path, min_interval=MIN_INTERVAL):
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            elapsed = time.time() - float(lock_path.read_text().strip())
            if elapsed < min_interval:
                wait = min_interval - elapsed
                print(f"[baidu] 等待 {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
        except:
            pass


def update_lock(lock_path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(time.time()))


def _search_baidu(query, max_results=10):
    """SearXNG + Baidu"""
    from urllib.request import Request, urlopen
    lock_path = get_lock_path()
    wait_if_needed(lock_path)
    try:
        q = url_quote(query)
        url = f"{SEARXNG_URL}/search?q={q}&engines=baidu&format=json"
        req = Request(url)
        resp = urlopen(req, timeout=SEARCH_TIMEOUT)
        raw = json.loads(resp.read().decode())
        update_lock(lock_path)
        results = []
        for r in raw.get("results", [])[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "href": r.get("url", ""),
                "body": r.get("content", ""),
            })
        return results
    except Exception as e:
        update_lock(lock_path)
        print(f"[baidu] {e}", file=sys.stderr)
        return []


def _search_firecrawl(query, max_results=10):
    """Firecrawl keyless"""
    try:
        from firecrawl.v2.client import FirecrawlClient
        client = FirecrawlClient()
        result = client.search(query)
        results = []
        for r in result.web[:max_results]:
            results.append({
                "title": r.title or "",
                "href": r.url or "",
                "body": r.description or "",
            })
        return results
    except Exception as e:
        print(f"[firecrawl] {e}", file=sys.stderr)
        return []


def search(query, max_results=10, json_output=False):
    """双引擎并行搜索 → 合并去重（Firecrawl 优先）"""
    results = []
    seen = set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fc_fut = pool.submit(_search_firecrawl, query, max_results)
        bd_fut = pool.submit(_search_baidu, query, max_results)

        for fut in [fc_fut, bd_fut]:
            try:
                for r in fut.result(timeout=SEARCH_TIMEOUT + 5):
                    href = r.get("href", "")
                    if href and href not in seen:
                        seen.add(href)
                        results.append(r)
            except Exception as e:
                print(f"[dual] {e}", file=sys.stderr)

    results = results[:max_results]

    if json_output:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for i, r in enumerate(results, 1):
            print(f"{i}.")
            print(f"title       {r['title']}")
            print(f"href        {r['href']}")
            print(f"body        {r['body']}")
            print()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="双引擎安全搜索 (Firecrawl + Baidu)")
    parser.add_argument("-q", "--query", required=True, help="搜索词")
    parser.add_argument("-m", "--max-results", type=int, default=10, help="最大结果数")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    search(args.query, args.max_results, args.json)


if __name__ == "__main__":
    main()
