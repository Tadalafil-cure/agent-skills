# Botasaurus 集成 — deep-search 提取层增强

> 2026-07-02：首装验证通过。Botasaurus 填补 scrapling (HTTP) 与 browser_navigate (慢) 之间的空白 —— 反检测 + 并行 + JS 渲染。

## 定位

| 层级 | 工具 | 适用场景 |
|:--:|------|---------|
| 1 | urllib + re | 无反爬的新闻/博客（最快） |
| 2 | scrapling | 轻反爬，HTTP 层绕过 |
| **2.5** | **Botasaurus @browser** | **Cloudflare/JS渲染/需要反检测** |
| 3 | browser_navigate | 微信/东方财富等特定站点 |
| 4 | Firecrawl | 前4层全挂的关键URL |

## 安装

```bash
pip install botasaurus
# 需要 Chromium（headless 服务器）：
sudo dnf install -y chromium-headless chromium
sudo ln -sf /usr/bin/chromium-browser /usr/bin/google-chrome
```

`@request` 装饰器需要 CGO 原生库（~13MB），首次 import 自动从 GitHub 下载。外网受限时需手动下载放到 `botasaurus_requests/bin/`。

## 核心装饰器

```python
from botasaurus.browser import browser, Driver

@browser(
    headless=True,
    parallel=5,                              # 并发数
    add_arguments=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    cache=True,                              # 磁盘缓存，不重复爬
)
def scrape_page(driver: Driver, url: str):
    driver.google_get(url)                   # Google Referrer 绕过基础反爬
    return {
        'url': url,
        'title': driver.get_text('h1'),
    }
```

## ⚠️ API 陷阱（踩坑记录）

### 1. 参数名是 `add_arguments` 不是 `arguments`
```python
# ❌ TypeError: browser() got an unexpected keyword argument 'arguments'
@browser(arguments=['--no-sandbox'])

# ✅ 正确
@browser(add_arguments=['--no-sandbox'])
```

### 2. Element 不支持链式选择
Botasaurus 的 Element 对象**没有** `select_one()` / `query_selector()` 方法。选择器只能通过 `driver` 调用：

```python
# ❌ AttributeError: 'Element' object has no attribute 'select_one'
h3 = g.select_one('h3')

# ✅ 用 driver.get_text('嵌套选择器')
title = driver.get_text('.g h3')
```

### 3. Element 不可 JSON 序列化
不能把 Element 传给 `driver.run_js()` 作为参数：

```python
# ❌ TypeError: Object of type Element is not JSON serializable
driver.run_js('return arguments[0].innerText', element)

# ✅ 最佳实践：用 JS 一次性提取全部数据
results = driver.run_js("""
    return Array.from(document.querySelectorAll('.g')).map(el => ({
        title: el.querySelector('h3').innerText,
        url: el.querySelector('a').href,
        snippet: el.querySelector('.s').innerText
    }));
""")
```

### 4. Cache 是模块级单例
```python
# ❌ TypeError: Cache() takes no arguments
cache = Cache('namespace')

# ✅ 模块级调用
import botasaurus.cache as cache_mod
cache_mod.Cache.put(key, data)
value = cache_mod.Cache.get(key)
```

### 5. Cloudflare 穿透
```python
driver.google_get(url, bypass_cloudflare=True)  # 处理 JS+CAPTCHA 挑战
```

## 反检测验证

Botasaurus Driver 默认 `navigator.webdriver = False`，比 undetected-chromedriver 多注册浏览器插件（5个），更接近真实浏览器。

## 与 deep-search 工作流集成

```
每轮搜索 → 筛选有价值 URL
  → 第 1 层：urllib 抓取（主力）
  → 第 2 层：scrapling 重试
  → 第 2.5 层：Botasaurus @browser 穿透反爬 ← 新增
  → 第 3 层：browser_navigate 兜底
```

典型触发场景：urllib 返回 403/空白 → scrapling 也失败 → 大概率是 Cloudflare/JS 渲染保护 → Botasaurus。
