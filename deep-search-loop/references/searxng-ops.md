# SearXNG 运维知识库

> deep-search v1.9 配套 —— 2026-06-28 集成实战沉淀

## 环境

| 项目 | 值 |
|------|-----|
| 源码 | `/home/admin/searxng/` |
| 配置 | `/home/admin/.searxng/settings.yml` |
| 端口 | `127.0.0.1:8880` |
| Python | system python3 |

## 启动命令

```bash
# 1. 杀僵尸进程
fuser -k 8880/tcp 2>/dev/null

# 2. 启动（必须 -u 去缓冲）
cd /home/admin/searxng && \
  SEARXNG_SETTINGS_PATH=/home/admin/.searxng/settings.yml \
  PYTHONPATH=. python3 -u searx/webapp.py
```

## ⛔ 禁止操作：YAML dump 覆写 settings.yml

```python
# ❌ 绝对禁止 —— 会丢失 disabled 字段、破坏缩进、所有引擎变 disabled
with open('settings.yml', 'w') as f:
    yaml.dump(cfg, f)

# ✅ 正确做法：用 patch 工具精确行编辑
# 或者用 Python 只读 YAML、不改写
cfg = yaml.safe_load(open('settings.yml'))
# ... 只读取，不写回
```

**后果**：YAML dump 后 `/config` 端点返回全部引擎 `enabled=False`，搜索返回 0 条。

## 引擎状态（2026-06-28）

| 引擎 | 配置 | 运行时 | 说明 |
|------|:--:|:--:|------|
| bing | `disabled: false` + `base_url: cn.bing.com` | ✅ | 主力，10 条/查询 |
| 360search | `disabled: false` | ⚠️ | 可用不稳定 |
| baidu | `disabled: false` | ⚠️ CAPTCHA | 偶尔放行 |
| sogou | `disabled: false` | ⚠️ CAPTCHA | 偶尔放行 |

**铁律**：引擎全开，不禁用。垃圾在 `filter_noise()` 拦截。

## 验证命令

```bash
# 搜索测试（英文必通）
curl -s "http://127.0.0.1:8880/search?format=json&q=TGV+glass" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  print(f'{len(d[\"results\"])} results, engines: {set(r[\"engines\"] for r in d[\"results\"])}')"

# 配置状态
curl -s "http://127.0.0.1:8880/config" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  [print(f'{e[\"name\"]:12s} enabled={not e.get(\"disabled\",True)}') for e in d['engines'] if e['name'] in ('bing','baidu','360search','sogou')]"
```

## 已知问题

- **baidu CAPTCHA**：`unresponsive: [['baidu', 'Suspended: CAPTCHA']]`——非配置问题，是运行时反爬拦截
- **sogou CAPTCHA**：同上
- **360search 不稳定**：有时返回 0 条，有时能出英文结果
- **中文长查询偏航**："玻璃基板"→音标词典。必须拆短词 ≤3 词
