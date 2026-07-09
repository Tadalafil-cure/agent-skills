# Firecrawl Keyless 接入指南

> deep-search v3.2 起集成 Firecrawl 作为第二搜索引擎 + 抓取兜底。

## 核心发现

**Firecrawl v2.11.0（2026-06）起支持 keyless 访问核心端点**：`/scrape`、`/search`、`/interact`、`/parse` 不需要 API Key。
从官方 SDK 客户端调用即可使用免费层（IP 限频）。

## 安装

```bash
pip install firecrawl-py
```

## 初始化

```python
from firecrawl.v2.client import FirecrawlClient

# keyless：不传 api_key
client = FirecrawlClient()
```

注意：必须用 `FirecrawlClient`（v2 client）。顶层 `Firecrawl()` 因 v1 兼容层会要求 API Key。

## 搜索

```python
result = client.search("微通道散热")
# result.web → list[SearchResultWeb]
# 每个 SearchResultWeb: .title, .url, .description
for item in result.web:
    print(item.title, item.url, item.description)
```

返回结构：
- `result.web` — 网页搜索结果（list）
- `result.news` — 新闻结果（list）
- 每页默认 ~8 条

## 抓取

```python
result = client.scrape("https://example.com")
md = result.markdown  # 清洗后的 Markdown
```

Firecrawl scrape 自带 headless browser（Playwright），能处理 JS 渲染页面。

## 与 SearXNG 对比（2026-06-28 实测）

| 维度 | SearXNG 国内引擎 | Firecrawl keyless |
|------|:--|:--|
| 中文搜索源 | 360百科/文库（垃圾） | IEEE/ScienceDirect/Nature/INFN |
| 英文搜索源 | 雪球/头条 | IEEE/ScienceDirect/Purdue/学术期刊 |
| 结果相关性 | 低（CAPTCHA+退化） | 高（全学术/技术源） |
| 百度 | CAPTCHA（suspended_time=3600） | 无需关心 |
| 稳定性 | 极差 | 极好（代理轮转无感） |
| JS 渲染 | 不支持 | 支持（Playwright） |
| 费用 | 免费 | 免费（keyless，IP 限频） |

**结论：Firecrawl 全面碾压 SearXNG。** SearXNG 保留作为备份/互补。

## 速率限制

Keyless 免费层有 IP 级别的速率限制。具体限制未文档化。实测 6 轮搜索（每轮间隔 2s）正常。

超量后错误：`429 Too Many Requests`。

## 适用场景

- **搜索：** `client.search()` 替换 SearXNG 的文本搜索
- **抓取：** `client.scrape()` 作为 scrapling 失败后的兜底
- **不适用：** 高频批量场景 → 需注册 API Key 付费层

## 架构决策

在 deep-search v3.2 中：
- SearXNG + Firecrawl **并行**搜索，共用 URL 去重
- 抓取阶段：scrapling（免费无限制）优先 → Firecrawl scrape（keyless）兜底
- 节约策略：Firecrawl 仅用于 scrapling 失败的 URL
