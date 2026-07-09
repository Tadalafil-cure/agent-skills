# 搜索工具可用性诊断 — 2026-06-28

## 工具状态

| 工具 | 状态 | 原因 |
|------|:--:|------|
| **web_search** | ✅ 已配置 | `hermes tools list` 显示 `web` toolset enabled。但需 `/reload` 或重启会话加载。由 Hermes 内置提供，背后可能是 SearXNG/Brave/DDG 等后端。 |
| **ddgs** (Python库) | ❌ 不可用 | 阿里云服务器 TCP 出站被墙，所有海外搜索引擎 timeout。走 `terminal` 调用 ddgs Python 库也不行——同样依赖出站 TCP。 |
| **SearXNG** | ⚠️ 退化 | `127.0.0.1:8880` 运行中。国内引擎：baidu/sogou 永久 CAPTCHA。360search/bing 偶尔可用但中文查询返回空。英文查询比中文好。`settings.yml` 已回滚干净配置，不要动。 |
| **Firecrawl keyless** | ⚠️ 日限频 | IP 日免费额度有限（~几十 credits）。搜索和抓取都消耗额度。适合兜底，不适合主力。 |
| **browser** | ⚠️ 不稳定 | `browser_navigate` daemon 偶发起不来。作为搜索引擎入口不可靠。更适合读具体页面。 |

## 推荐搜索策略

1. **首选 `web_search`**（Hermes 内置）—— 确保 session 重启后加载
2. **备选 SearXNG 英文** —— `engines=bing,360search&language=en`
3. **兜底 Firecrawl** —— 仅 1 次，省额度
4. **不推荐 browser 搜索引擎** —— daemon 不稳定

## 工具发现过程

`hermes tools list` → `web` toolset enabled → 但当前会话未加载 web_search 工具 → 需要 `hermes gateway restart` 重开会话。
