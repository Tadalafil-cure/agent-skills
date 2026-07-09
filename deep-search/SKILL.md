---
name: deep-search
description: Agent 驱动的深度搜索与阐述报告 —— 用户给主题，Agent 用工具搜、读、判断、合成，最少 3 轮最多 6 轮自适应终止，输出阐述性分析报告。
version: 5.4.0
trigger_keywords: [搜索, 查一下, 搜一下, 深度搜索, deep search, 帮我搜, 研究一下, 调研, 查查]
---

# deep-search v5.4

> v5.4：降级链铁律 — 每篇 URL 必须走完 L1→L2→L2.5→L3→L4，禁止"L1 失败就跳过"。每轮 ≥5 篇。新增站点分层速查表。v5.3：强制最少 3 轮

## 核心原则

- **主力搜索：SearXNG → baidu JSON API**。用 `execute_code` 调 urllib 直连 `127.0.0.1:8880`，不走 terminal 避免审批。每轮走中文 + 英文两路搜索，结果合并去重。
- **英文补充：arXiv API**。`execute_code` + urllib 直连 `arxiv.org`。
- **停用后端不纠结**：ddgs / web_search / cn.bing.com / 360search / sogou / bing 全部不可用，不要试。Firecrawl 可用 keyless 模式（`FirecrawlClient()`，无需 API key）。
- **输出是阐述报告**：结构化分析，有数据有对比有判断有出处。不是 dump。
- **🔥 降级链铁律（v5.4）**：每一篇 URL 必须走完降级链。L1 失败 → L2 → L2.5 → L3 → L4。**禁止"L1 失败就跳过"**。已知站点查 `references/site-layer-map.md` 直接跳对应层，未知站点逐层试到底。每轮至少抓取 5 篇正文，不够就继续降级。

## 工作流

### Step 0：保活检查（每次任务强制先跑）

用 `execute_code` 执行。**不能只探 `/config`——SearXNG 可能返回 200 但搜索已假死。必须做搜索测试：**

```python
import urllib.request, subprocess, time, json

# ① 探活
try:
    urllib.request.urlopen("http://127.0.0.1:8880/config", timeout=3)
    config_ok = True
except:
    config_ok = False

# ② 搜索测试（关键——config 200 ≠ 搜索正常）
search_ok = False
if config_ok:
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:8880/search?q=test&engines=baidu&format=json", timeout=10)
        d = json.loads(resp.read())
        search_ok = len(d.get('results', [])) > 0
    except:
        pass

# ③ config 200 但搜索 0 结果 → 假死，必须重启
if config_ok and not search_ok:
    print("SearXNG 假死——搜索返回 0，重启...")
    config_ok = False

# ④ 挂了/假死 → 拉起
if not config_ok:
    subprocess.Popen(
        ["python3", "-m", "searx.webapp"],
        cwd="/home/admin/searxng",
        env={"SEARXNG_SETTINGS_PATH": "/home/admin/.searxng/settings.yml", "PATH": "/usr/bin:/usr/local/bin"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(8)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:8880/search?q=test&engines=baidu&format=json", timeout=10)
        d = json.loads(resp.read())
        print(f"baidu: {len(d.get('results',[]))} results — SearXNG READY")
    except Exception as e:
        print(f"SearXNG start failed: {e}")
else:
    print("SearXNG OK")
```

**禁止的启动命令（已验证失败）：**
- ❌ `python3 searx/webapp.py` → ModuleNotFoundError
- ❌ `python3 manage run` → SyntaxError
- ✅ 唯一可靠：`python3 -m searx.webapp` + 环境变量

**⚠️ SearXNG 假死 vs CAPTCHA 陷阱（v5.4 更新）：** `/config` 返回 200 ≠ 搜索正常。搜索返回 0 有两种可能：① SearXNG 假死（进程异常）→ 重启有效；② 百度 CAPTCHA（IP 封禁）→ **重启无效，只能等 suspended_time 过期**。区分方法：查看 SearXNG stderr 日志是否含 `CAPTCHA (suspended_time=...)`。含 → 是 CAPTCHA，不要反复重启。不含 → 假死，重启。详见 `references/searxng-fake-dead.md`。

### Step 1：分析主题 → 制定搜索计划

理解主题后，规划 6 个搜索角度：

| # | 角度 | 典型搜索方向 | 中文词示例 | 英文词示例 |
|---|------|-------------|-----------|-----------|
| 1 | 定义与概述 | 是什么、核心参数、分类 | `<主题> 是什么 原理` | `what is <topic>` |
| 2 | 原理与技术 | 怎么工作、技术路线、关键指标 | `<主题> 技术原理 结构` | `<topic> technology mechanism` |
| 3 | 应用与场景 | 用在哪儿、典型案例 | `<主题> 应用 场景 案例` | `<topic> application use case` |
| 4 | 产业链与厂商 | 上下游、主要玩家、市场规模 | `<主题> 产业链 厂商 市场` | `<topic> industry market vendor` |
| 5 | 进展与动态 | 最新突破、趋势、2025-2026 | `<主题> 最新 进展 2025` | `<topic> latest breakthrough 2025` |
| 6 | 竞争与挑战 | 替代方案、瓶颈、争议 | `<主题> 对比 替代 挑战` | `<topic> alternative comparison challenge` |

### Step 2：执行搜索（最少 3 轮，最多 6 轮自适应终止）

**关键词策略：百度 ∥ cn.bing 并发，各自独立迭代。**
- R1：两路径共用同一组初始关键词
- R2 起：**各自从自己的前轮结果提炼关键词**，两个关键词可以完全不同
- 结果去重合并，互补覆盖
- ⚠️ **cn.bing 不可靠**：同一查询两次可能返回完全不同结果（金属网格 vs Microsoft 官网）。结果随机、不可控。只当锦上添花，不以它为主力。百度恢复后优先百度

```
每轮流程（用 execute_code 一次性执行）：
  ① 确定本轮搜索词
  ② 并发：SearXNG 百度 + cn.bing.com 直连
  ③ 去重合并 → 筛选有价值 URL
  ④ 抓取正文（urllib → scrapling → browser 分层）
  ⑤ 提取关键信息 + 缺口分析
  ⑥ 判断终止
```

**每轮搜索实现（execute_code 模板）：**

```python
import urllib.request, urllib.parse, json, re, time

query_baidu_cn = "<百度中文关键词——从上一轮结果提炼>"
query_baidu_en = "<百度英文关键词——从上一轮结果提炼>"
query_bing     = "<cn.bing关键词（仅英文有效）>"

# === SearXNG baidu 中文搜索 ===
encoded_cn = urllib.parse.quote(query_baidu_cn)
url_cn = f"http://127.0.0.1:8880/search?q={encoded_cn}&engines=baidu&format=json"
resp_cn = urllib.request.urlopen(urllib.request.Request(url_cn), timeout=15)
data_cn = json.loads(resp_cn.read().decode())
results_cn = data_cn.get("results", [])
print(f"baidu CN: {len(results_cn)} results")

# === SearXNG baidu 英文搜索 ===
encoded_en = urllib.parse.quote(query_baidu_en)
url_en = f"http://127.0.0.1:8880/search?q={encoded_en}&engines=baidu&format=json"
resp_en = urllib.request.urlopen(urllib.request.Request(url_en), timeout=15)
data_en = json.loads(resp_en.read().decode())
results_en = data_en.get("results", [])
print(f"baidu EN: {len(results_en)} results")

# === 合并筛选 ===
all_results = []
for r in results_cn + results_en:
    url_r = r.get("url", "")
    # 跳过低质量源
    skip = ["wenku.baidu.com", "jingyan.baidu.com", "zhidao.baidu.com"]
    if any(d in url_r for d in skip):
        continue
    all_results.append({
        "title": r.get("title", ""),
        "url": url_r,
        "content": r.get("content", "")[:300],
        "engine": r.get("engine", "")
    })

# 打印供 Agent 判断
for i, v in enumerate(all_results[:10], 1):
    print(f"\n{i}. [{v['engine']}] {v['title'][:100]}\n   {v['url'][:120]}\n   {v['content'][:200]}")

# === 缺口分析（每轮必做，决定是否继续） ===
print("\n\n=== 缺口分析 ===")
print("本轮覆盖角度：<列出已获取信息的6个角度覆盖情况>")
print("浅层需深挖：<列出只有泛泛介绍、缺具体数据的方向>")
print("中层待补细节：<列出有数据但缺细分/对比/因果的角度>")
print("深层已饱和：<列出可关闭的角度>")
print("下轮方向：<基于缺口定下轮搜索词>")
```
# === arXiv 搜索（仅需要学术支撑时启用） ===
# arxiv_url = f"https://arxiv.org/search/?query={urllib.parse.quote(query_en)}&searchtype=all"
# req = urllib.request.Request(arxiv_url, headers={"User-Agent": "Mozilla/5.0"})
# resp = urllib.request.urlopen(req, timeout=20)
# html = resp.read().decode()
# ids = re.findall(r'arxiv:(\d+\.\d+)', html)
# titles = re.findall(r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>', html, re.DOTALL)
# for i in range(min(3, len(ids), len(titles))):
#     t = re.sub(r'<[^>]+>', '', titles[i]).strip()
#     print(f"\n[arXiv:{ids[i]}] {t[:150]}")
```

**终止条件（R1-R3 强制执行不判断。R4 起任一触发就停，6 轮是硬上限）：**

**不是简单数角度。每轮抓取完正文后，必须逐条评估信息深度：**

```
深度判定（每轮结束时执行）：
  对每个已覆盖的角度：
    浅层覆盖 = 只有标题/摘要/泛泛介绍 → 下一轮需要深挖
    中层覆盖 = 有具体数据但缺细节（如"市场规模X亿"但无细分/增速/驱动因素）
    深层覆盖 = 有数据+有对比+有出处+有因果关系 → 该角度已饱和

终止判断：
  - R1、R2、R3：不做终止判断，必须继续（保底覆盖 6 个角度）
  - R4 起，三选一触发立即停：
    - 全部活跃角度的深层覆盖率 ≥ 80% → 立即停
    - 连续 2 轮无新增深层信息 → 立即停（说明搜索引擎已穷尽）
    - 跑满 6 轮 → 保底终止
```

**每轮末尾必做：列出缺口 → 决定下轮方向。** 如果"产业链"角度只有"市场规模 21 亿"一句话，下一轮必须用更具体的词深挖（如"微通道换热器 细分市场 汽车空调 数据中心 占比"）。如果某个角度已经够深，换角度。

**核心原则：R1-R3 是强制覆盖——不能因为前 2 轮信息看起来够了就停。R4 起信息够了就停，不要为了凑轮数多搜。**

### Step 3：抓取正文（分层兜底，按需抓取）

搜到的有价值 URL 需要读正文。**不设数量上限——以信息饱和度为判据**：一个 URL 的正文如果已经覆盖了本轮搜索目标，不需要再开下一个。

按以下优先级分层：

| 优先级 | 工具 | 调用 | 适用 | 额度 |
|:--:|------|------|------|:--:|
| 1 | **execute_code + urllib** | HTTP GET，re 去标签 | 新闻/博客/CSDN/知乎。最快，不用审批 | 免费 |
| 2 | **scrapling** | `terminal: scrapling extract get/fetch` | urllib 返回空白/轻反爬 | 免费 |
| 2.5 | **Botasaurus @browser** | `parallel=5, cache=True` | Cloudflare/JS渲染/反检测。API陷阱见 `references/botasaurus-integration.md` | 免费 |
| 3 | **browser_navigate** | Agent 自带 | 微信/东方财富等特定站点 | 免费 |
| 4 | **arXiv API** | urllib → arxiv.org | 仅学术论文深度支撑 | 免费 |
| 5 | **Firecrawl scrape** | 需 API key | 前 5 层全挂的关键 URL | ⚠️ 消耗额度 |
| 6 | **browser-act** | 手动触发 | 不在自动流程中 | ⚠️ 消耗额度 |

**优先免费。Firecrawl 和 browser-act 只在前面全挂 + 信息不可或缺时才用。**

⚠️ `web_extract` 不可用（底层 ddgs 被墙），不要调。

**循环抓取：逐个 URL 读正文，信息饱和即停。每轮 ≥5 篇。不够就继续降级——工具给了就要用。**

**⚠️ 已知站点优化**：查 `references/site-layer-map.md`。百家号/澎湃/搜狐/新浪/腾讯/东财财富号 → 直接 L1。雪球/知乎专栏 → 直接 L2.5 Botasaurus。新域名走完整降级链。

**第 1 层：execute_code + urllib（主力，最快）**

```python
import urllib.request, re

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

failed_urls = []  # 记录失败 URL 供降级

for url in urls_to_fetch[:5]:
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        # 去标签提取正文
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'&nbsp;|&ensp;|&emsp;', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean)
        # 过滤掉导航/页脚等杂讯：只保留正文密集区域
        if len(clean) < 300:
            failed_urls.append((url, "content too short"))
            continue
        print(f"\n{'='*40}\nURL: {url}\n{clean[:3000]}")
    except Exception as e:
        failed_urls.append((url, str(e)[:100]))
        print(f"\n{'='*40}\nURL: {url}\nFAIL: {e} — 降级到第 2 层")

# 输出失败列表，供后续层处理
if failed_urls:
    print(f"\n⚠️ 第 1 层失败 {len(failed_urls)} 个 URL，需降级处理")
```

**第 2 层：scrapling（terminal 调用，比 browser 快）**

第 1 层失败的 URL 用 scrapling 重试：

```bash
# 对每个失败 URL 逐个尝试
scrapling extract get 'https://example.com/article' /tmp/scrape_output.md
# 或
scrapling extract fetch 'https://example.com/article' /tmp/scrape_output.md
```

⚠️ scrapling 有 2 层模式：HTTP（`get`）→ JS 渲染（`fetch`）。先 `get`，失败再 `fetch`。

**第 3 层：browser_navigate（JS 渲染页面兜底）**

scrapling 也失败时，用 `browser_navigate` 打开：
- 微信文章（mp.weixin.qq.com）
- 东方财富（eastmoney.com）
- 需要登录/Cookie 的页面

browser daemon 启动失败 → 继续降级，不阻塞。

**第 4 层：arXiv API（论文专用）**

```python
req = urllib.request.Request(
    f"https://arxiv.org/abs/{paper_id}",
    headers={"User-Agent": "Mozilla/5.0"}
)
resp = urllib.request.urlopen(req, timeout=20)
html = resp.read().decode()
abs_match = re.search(
    r'<blockquote class="abstract[^"]*">\s*<span class="descriptor">Abstract:</span>\s*(.*?)</blockquote>',
    html, re.DOTALL
)
if abs_match:
    abstract = re.sub(r'<[^>]+>', '', abs_match.group(1)).strip()
```

**第 5 层：Firecrawl（需 API key，谨慎使用）**

仅前 4 层全失效 + 该 URL 是关键信息源时使用。无 key 则跳过。

**第 6 层：browser-act（手动触发）**

终报时列出所有仍未抓取的 URL，询问用户：

> 以下 N 个 URL 自动抓取失败，是否启用 browser-act 手动打开？
> 1. https://...
> 2. https://...

### Step 4：合成报告

读完素材后，按以下结构写阐述性报告：

1. **是什么** — 定义、核心参数、分类方式
2. **原理与技术路线** — 怎么工作、主要技术分支、关键指标对比表
3. **应用场景** — 用在哪儿、典型案例（有数据/有出处）
4. **产业格局** — 产业链、主要玩家、市场规模
5. **前沿进展与挑战** — 2025-2026 最新动态、瓶颈、争议
6. **来源清单** — 每条标注来源 URL 和获取状态

**质量铁律：**
- 数据必须有对比表
- 论断必须标注出处
- 有"为什么"不只是"是什么"
- 局限性坦诚标注（数据源缺失、纯学术无产业等）

### Step 5：交付

- 对话中直接贴报告
- 同时写 `final_report.md` 到 `/home/admin/file-transfer/<主题>_report.md`

## 安全规则

| 规则 | 说明 |
|------|------|
| **轮间间隔** | 每轮之间 ≥25s。把本轮耗时算进去：如果一轮跑了 10s，额外再等 15s |
| **轮内请求数** | **每轮 2 个查询**：1 个走 SearXNG 百度 + 1 个走 cn.bing.com 直连。路径之间 ≥5s。不在同一条路径内连发 |
| **轮内查询间隔** | 两个查询之间 ≥5s |
| **首轮 0 结果探因** | 首轮百度返回 0 → 分类处理：①看 SearXNG stderr 含 `CAPTCHA` → 百度 IP 被封，**切 Firecrawl keyless** (`firecrawl.v2.client.FirecrawlClient()`)；② stderr 无 CAPTCHA → SearXNG 假死，重启。cn.bing 不可靠，不推荐 |
| **arXiv 保护** | 每轮 ≤3 次搜索请求，间隔 ≥5s |
| **抓取节制** | 不设数量硬限制，但以信息饱和度为判据——读完一个 URL 正文后判断是否已覆盖本轮目标，够了就不开下一个 |
| **失败不纠缠** | SearXNG+baidu 连续 2 轮 0 结果 → 只走 arXiv，不停诊断。3 轮内找不到可用源就认输 |
| **禁止选项** | `web_search` / `ddgs` / `cn.bing.com` 全部不可用，不要试 |

## 可用搜索后端

| 优先级 | 工具 | 调用方式 | 适用 |
|:--:|------|---------|------|
| **1** | **SearXNG + baidu** | `execute_code` + urllib → `127.0.0.1:8880` | **主力**。中英文技术搜索，8-10 条高质量结果 |
| **2** | **Firecrawl keyless** | `from firecrawl.v2.client import FirecrawlClient; FirecrawlClient().search()` | 百度 CAPTCHA 时主力替代。研报/产业数据/市场报告。无需 API key |
| **3** | **arXiv API** | `execute_code` + urllib → `arxiv.org` | 仅学术论文深度支撑 |
| ❌ | cn.bing.com 直连 | — | 结果随机不可靠，不推荐 |
| ❌ | ddgs CLI | — | 解析器不兼容，返回 None |
| ❌ | web_search | — | DuckDuckGo API 被墙 |

## ⛔ 禁止事项

- ❌ 调 `scripts/deep_search.py` 或任何脚本
- ❌ dump 原始抓取内容当报告
- ❌ 6 轮盲跑、不读结果、不调整搜索词
- ❌ 修 SearXNG 配置
- ❌ 一轮搜几十个 URL 全打开
- ❌ 搜到结果不读正文就写报告
- ❌ 向用户报告"X 后端失败了、Y 也不可用"——直接 pivot，不废话
- ❌ 报告失败而不产出——即使只剩 arXiv 也要出报告

## 参考文件

- `references/botasaurus-integration.md` — Botasaurus 反检测浏览器提取层集成 + API 陷阱速查
- `references/site-layer-map.md` — 🔥 站点分层速查表（积累自实战，已知站点直接跳对应层）
- `references/backend-state-2026-06-28.md` — 搜索后端连通性图谱
- `references/direct-url-fallback.md` — execute_code + urllib 直连方案
- `references/mlcp-case.md` — 微通道散热高质量报告参考案例
