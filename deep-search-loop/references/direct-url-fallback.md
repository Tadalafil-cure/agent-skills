# direct-url-fallback: execute_code + urllib 终极兜底

当全部搜索后端都不可用时，用 `execute_code` + Python `urllib` 直连已知可访问的信息源。

## 适用场景

- `web_search` 不可用（ddgs 后端被墙，SearXNG 全死，Firecrawl 额度耗尽）
- browser daemon 起不来
- 服务器在中国大陆阿里云，部分海外站点被墙

## 步骤

### 1. 先探测连通性（terminal）

```bash
curl -s -o /dev/null -w "%{http_code} %{time_total}s" --connect-timeout 5 \
  "https://arxiv.org" && echo " OK" || echo " FAIL"
```

已知结果（阿里云北京，2026-06-28）：
- arxiv.org ✓ (200, 0.9s)
- baidu.com ✓ (200, 0.05s) — 但搜索请求超时
- bing.com ✓ (302, 0.2s) — 但中文搜索返回垃圾
- zhihu.com ✓ (302, 0.1s)
- google.com ✗ (timeout)
- yahoo.com ✗ (timeout)
- startpage.com ✗ (timeout)

### 2. execute_code 直接搜 arXiv

```python
import urllib.request, urllib.parse, re

query = "microchannel heat sink cooling"
encoded = urllib.parse.quote(query)
url = f"https://arxiv.org/search/?query={encoded}&searchtype=all&start=0"

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=20)
html = resp.read().decode('utf-8', errors='replace')

# Extract paper info
title_pat = re.compile(r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>', re.DOTALL)
titles = title_pat.findall(html)
arxiv_ids = re.findall(r'arXiv:(\d+\.\d+)', html)

for i in range(min(len(titles), len(arxiv_ids))):
    t = re.sub(r'<[^>]+>', '', titles[i]).strip()
    print(f"[{arxiv_ids[i]}] {t}")
```

### 3. 获取单篇论文摘要

```python
pid = "2603.09607"
url = f"https://arxiv.org/abs/{pid}"

resp = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20)
html = resp.read().decode('utf-8', errors='replace')

# Title
t = re.search(r'<h1 class="title[^"]*">(.*?)</h1>', html, re.DOTALL)
title = re.sub(r'<[^>]+>', '', t.group(1)).strip() if t else 'N/A'

# Abstract
a = re.search(r'<blockquote class="abstract[^"]*">.*?<span class="descriptor">Abstract:</span>\s*(.*?)</blockquote>', html, re.DOTALL)
abstract = re.sub(r'<[^>]+>', '', a.group(1)).strip() if a else 'N/A'
```

### 4. 多轮搜索策略

- 先搜 broad query → 读标题识别相关论文
- 根据论文关键词调整第二轮搜索词
- 搜 2-3 轮即可（arXiv 论文量不如通用搜索引擎大）
- 每轮至少间隔 3s

## ⚠️ 已知坑

1. **f-string 中不能用 backslash** → 先把 regex 赋给变量或 compile
2. **Bing 对中文技术词搜索返回垃圾**（"微通道散热" → "微信"+"通道"）→ 仅用英文搜 Bing
3. **Baidu 搜索请求超时 300s**（反爬）→ 不可用
4. **Wikipedia 从阿里云不通**（SSL handshake timeout）
5. **arXiv 搜索有时返回 0 结果**但标题里有匹配 → 检查 `Showing X of Y results` 确认，有时 HTML 解析模式不匹配
