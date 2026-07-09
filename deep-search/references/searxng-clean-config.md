# SearXNG 干净配置 —— 最小化原则

*deep-search v1.10 收录 · 2026-06-28*

## 铁律

**禁止手动管理引擎的 `disabled` 字段。** 让 SearXNG 的 `use_default_settings: true` 管理引擎生命周期。

手动开关引擎的后果：
- 每次改 `disabled` 值都需要重启 SearXNG
- 修改过程中 YAML dump 容易破坏文件结构（缩进错位、字段丢失）
- 频繁重启触发搜索引擎反爬机制（CAPTCHA 冷却时间被反复重置）
- 手动启用的引擎可能用非默认参数（缺少内置的 rate-limit/cookie/header 优化）

## 正确的最小化配置

```yaml
# /home/admin/.searxng/settings.yml
use_default_settings: true

search:
  formats:
    - html
    - json

server:
  secret_key: "<random 32-char hex string>"
```

**只写这三个字段，其他全用默认。**

- `use_default_settings: true` — 继承 SearXNG 内置的所有引擎配置（含最佳 anti-bot 参数）
- `formats: [html, json]` — JSON 是 deep_search.py 的 API 入口
- `secret_key` — 必需，否则 SearXNG 无法启动

## 不需要写的

- `engines:` — **绝对不要写**。默认全部启用，引擎自带正确的 rate-limit/cookie/UA
- `general:` — 默认即可
- `server: limiter:` — 默认是 true，但服务器上 botdetection 缺文件会报 warning，可忽略或设为 false
- `server: bind_address / port` — 用 `SEARXNG_BIND_ADDRESS` 环境变量控制，不在 YAML 里写

## 启动命令

```bash
# 先杀僵尸
fuser -k 8880/tcp

# 启动（后台）
cd /home/admin/searxng
SEARXNG_SETTINGS_PATH=/home/admin/.searxng/settings.yml \
  PYTHONPATH=. python3 -u searx/webapp.py
```

## 验证命令

```bash
# 基本连通
curl -s -m 10 "http://127.0.0.1:8880/search?format=json&q=test" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('results',[])), 'results')"

# 查看不可用引擎
curl -s -m 10 "http://127.0.0.1:8880/search?format=json&q=test" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('unresponsive_engines',[]))"
```

## 引擎状态速查（本服务器 2026-06-28）

| 引擎 | 英文词 | 中文词 | 说明 |
|------|:--:|:--:|------|
| bing | ✅ | ❌ | 纯中文返回随机垃圾 |
| 360search | ⚠️ | ⚠️ | 不稳定，0-7 条 |
| baidu | ✅ | ❌ CAPTCHA | 英文词可用，中文触发反爬 |
| sogou | ❌ | ❌ | 固定 CAPTCHA |
| google/brave/DDG/yahoo 等 | ❌ | ❌ | 服务器出站 TCP 被墙 |

## 曾踩过的坑

1. **YAML dump 破坏文件**：`yaml.dump()` 写回 settings.yml 会导致 `disabled` 字段丢失、缩进变块风格（3506 行 → 2612 行）、SearXNG 解析失败
2. **手动开关引擎触发 CAPTCHA**：把 baidu/sogou 从 `disabled: false` ↔ `true` 反复切换，每次重启都会重触发反爬冷却
3. **端口僵尸**：旧 SearXNG 进程（用旧配置）霸占 8880 端口，新进程起不来。`fuser -k 8880/tcp` 是必做前置步骤
4. **sogou.py 改移动端无效**：CAPTCHA 是 IP 级别的，改 UA/移动端 URL 没用——`git checkout` 还原即可
