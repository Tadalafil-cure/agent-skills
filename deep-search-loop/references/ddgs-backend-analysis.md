# ddgs 后端分析：它不是什么，底层是什么

*2026-06-28 · 实测确认 · deep-search v5.0 收录*

## ddgs 是什么

`ddgs` 是 `duckduckgo_search` Python 包的 CLI 入口，安装在 hermes venv：

```
/home/admin/.hermes/hermes-agent/venv/bin/ddgs
→ from duckduckgo_search.cli import safe_entry_point
```

**不是自建工具，是开源库。**

## 两条路径，两个底层

| 调用路径 | 底层引擎 | 目前状态（阿里云中国区） |
|---------|---------|---------------------|
| `hermes web_search` 工具 | DuckDuckGo API → Yahoo / Startpage | ❌ Yahoo/Startpage TCP 出站被墙，超时 |
| `ddgs text -k` CLI | **Bing 直搜** | ⚠️ Bing 强制重定向 cn.bing.com → 返回垃圾 |

## ddgs CLI 的 Bing 后端行为

ddgs text 搜索走的是 Bing 的 HTML 搜索结果页（不是 API）。关键行为：

1. **强制重定向**：服务器中国 IP → Bing 自动重定向到 `cn.bing.com`，`cc=us` / `mkt=en-US` 参数被无视
2. **返回 None 是正确行为**：当 cn.bing.com 返回的 HTML 中无有效搜索结果时，ddgs 返回 `None`（这是 duckduckgo_search 库的保护逻辑，不是 bug）
3. **垃圾结果**：即使 Bing 返回 HTTP 200 + 10 个 `b_algo` 块，内容也与查询词完全无关（如搜 "microchannel cooling" 返回"抖音商品卡"）

## 为什么要区分两条路径

之前 session 中的困惑：错误日志里同时出现 Yahoo/Startpage timeout 和 Bing "return None"，给人感觉 ddgs 同时在调多个引擎。实际情况：

- `web_search` 工具走 DuckDuckGo API → 报 Yahoo/Startpage timeout
- `ddgs` CLI 走 Bing → 报 "return None"

**两者失败原因不同，但结果一样：从阿里云均不可用。**

## 最终结论

- ddgs 在阿里云环境下 **不可用**（无论是 web_search 路径还是 CLI 路径）
- 不要尝试修复 ddgs——不是配置问题，是网络环境 + Bing cn 质量双重夹杀
- 策略：web_search 失败 1 次 → 1 个备选失败 → **直接走 execute_code urllib 直连 arXiv**
