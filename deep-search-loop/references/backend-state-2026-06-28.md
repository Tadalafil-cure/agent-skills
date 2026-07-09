# 搜索后端连通性图谱 — 2026-06-28 实测

> 阿里云中国区服务器。每次搜索任务前先快速探测，不要凭记忆假设。

## 🔌 服务器网络连通性

| 站点 | HTTP | 延迟 | 可用 |
|------|:----:|------|:----:|
| baidu.com | 200 | 53ms | ✅ |
| bing.com | 302 | 218ms | ✅ (但强制重定向 cn.bing.com) |
| zhihu.com | 302 | 124ms | ✅ |
| arxiv.org | 200 | 940ms | ✅ |
| google.com | — | 5s 超时 | ❌ (被墙) |
| yahoo.com | — | 5s 超时 | ❌ (被墙) |
| startpage.com | — | 5s 超时 | ❌ (被墙) |
| wikipedia.org | — | 超时 | ❌ (被墙) |

## 📡 各搜索后端实测状态

### SearXNG（127.0.0.1:8880）

**启动命令**：
```bash
cd /home/admin/searxng && SEARXNG_SETTINGS_PATH=/home/admin/.searxng/settings.yml python3 -m searx.webapp
```
⚠️ `python3 manage run` 有语法错误，不要用。

**引擎状态**：

| 引擎 | 状态 | 说明 |
|------|:----:|------|
| **baidu** | ✅ **主力** | 返回 8-9 条中文高质量结果。技术词精确匹配。⚠️ 偶发 CAPTCHA，重试 1 次通常恢复 |
| 360search | ❌ 静默归零 | SearXNG 不报错、不标 unresponsive，直接返回 0 结果 |
| sogou | ❌ CAPTCHA | 明确报 `['sogou', 'CAPTCHA']` |
| bing | ❌ 静默归零 | 同 360search，0 结果无报错 |

**注意**：SearXNG 进程可能悄无声息地挂掉。所有引擎返回空时，先 `ps aux | grep searxng` 检查进程。

### ddgs (duckduckgo_search Python 包)

**调用链**：`ddgs text -k "query"` → `duckduckgo_search` 包 → **Bing 搜索**

不经过 Yahoo/Startpage。直接调 Bing，但被强制重定向到 cn.bing.com。

### cn.bing.com（Bing 中国版）

- 英文搜索技术词 → 返回垃圾（"抖音商品卡"、"Microsoft Support"等无关内容）
- 中文搜索技术词 → 同样垃圾（天气网、广西工业学院 sogou 百科）
- **结论**：cn.bing.com 对技术/学术类查询完全不可用。ddgs 返回 None 是 ddgs 解析器检测到无效结果主动报空，不是网络问题。

### web_search (Hermes 内置工具)

底层走 **DuckDuckGo API**（非 ddgs CLI），上游是 Yahoo + Startpage，均被墙。覆盖所有 web_search 相关工具（web_extract 同）。

### Firecrawl

- keyless 模式：日免费额度有限，搜索+抓取都消耗
- 带 API key：注册 https://firecrawl.dev 获得 key 后可正常使用，无额度限制

## 🎯 搜索策略（按此顺序）

```
1. SearXNG + baidu → 中文搜索首选，质量高
2. arXiv API (urllib 直连) → 英文学术内容
3. ⚠️ ddgs / web_search → 不可用，跳过
4. ⚠️ cn.bing.com → 不可用，跳过
5. Firecrawl (需要 API key) → 兜底全后端
```

## 📋 快速诊断脚本

```bash
# 检查 SearXNG 进程
ps aux | grep searxng | grep -v grep

# 测试 SearXNG 百度引擎
curl -s --connect-timeout 10 \
  "http://127.0.0.1:8880/search?q=test&engines=baidu&format=json" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('results',[])),'results')"

# 连通性探测
for site in baidu.com bing.com arxiv.org zhihu.com google.com; do
  curl -s -o /dev/null -w "$site %{http_code} %{time_total}s\n" --connect-timeout 5 "https://$site"
done
```
