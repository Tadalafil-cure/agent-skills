# SearXNG 安装与恢复指南

> deep-search v1.8 后端。ddgs 被墙时自动回退到此。

## 安装位置

```
源码目录：  /tmp/searxng/              (git clone)
设置文件：  /tmp/searxng/searx/settings.yml
启动方式：  PYTHONPATH=/tmp/searxng python3 searx/webapp.py
依赖：      msgspec, flask, httpx, lxml, pyyaml, valkey, etc.
```

## 启动命令

```bash
cd /tmp/searxng && PYTHONPATH=/tmp/searxng:$PYTHONPATH \
  /home/admin/.hermes/hermes-agent/venv/bin/python3 searx/webapp.py
```

监听 `127.0.0.1:8880`。验证：`curl http://127.0.0.1:8880/healthz` → `OK`

## 配置文件关键项

已在 `/tmp/searxng/searx/settings.yml` 中预置：

| 配置 | 值 | 位置 |
|------|-----|------|
| `server.port` | `8880` | L90 |
| `server.bind_address` | `127.0.0.1` | L91 |
| `server.secret_key` | 已改（非 `ultrasecretkey`） | L102 |
| `engines.baidu.disabled` | `false` | ~L518 |
| `engines.360search.disabled` | `false` | ~L302 |
| `engines.sogou.disabled` | `false` | ~L2168 |

## 已启用搜索引擎

- **百度** — 中文搜索主力
- **360搜索** — 备用
- **搜狗** — 备用
- **Bing** — HTTP 302 可达但引擎返 0 条（SearXNG quirk，非配置问题）
- 其他海外引擎全部 `disabled: true`

## 常见故障与恢复

### 1. 启动即退出：`secret_key is not changed`

```
ERROR:searx.webapp: server.secret_key is not changed.
Please use something else instead of ultrasecretkey.
```

**原因**：settings.yml 中 `secret_key` 为默认值。
**修复**：改 `secret_key: "ultrasecretkey"` 为随机字符串。

```bash
# 生成新 key
python3 -c "import secrets; print(secrets.token_hex(32))"
# 替换 settings.yml 中 L102 的 secret_key
```

### 2. 搜索返回 403 Forbidden

```
HTTP/1.0 403 FORBIDDEN
```

**原因**：引擎全部 disabled 或 settings.yml 不存在/损坏。
**检查**：`grep "disabled: false" /tmp/searxng/searx/settings.yml | wc -l`
应 ≥3（baidu/360search/sogou）。

### 3. 搜索返回 500：`KeyError: 'default_doi_resolver'`

```
KeyError: 'default_doi_resolver'
```

**原因**：用了旧版 settings.yml（缺少此字段）。
**修复**：用 `/tmp/searxng/searx/settings.yml`（git clone 自带），不要用 `/tmp/searxng-conf/settings.yml`（旧版）。

### 4. 源码目录被清理（`/tmp/searxng` 不存在）

**症状**：`FileNotFoundError: /tmp/searxng/searx/webapp.py`

**恢复步骤**：
```bash
cd /tmp
git clone https://github.com/searxng/searxng.git --depth 1
cd searxng
# 安装依赖
pip3 install msgspec flask httpx lxml pyyaml valkey
# 配置 settings.yml（找备份或重新编辑）
# 启用 baidu/360/sogou，设 port=8880，改 secret_key
# 启动
PYTHONPATH=/tmp/searxng python3 searx/webapp.py
```

### 5. `ModuleNotFoundError: No module named 'msgspec'`

**修复**：`pip3 install msgspec`

## 环境变量

```bash
export SEARXNG_URL=http://127.0.0.1:8880
```

`$SEARXNG_URL` 在 deep-search 协议中被引用。SearXNG 启动后必须可从此 URL 访问。

## 与 ddgs 的关系

```
ddgs（首选） → 连续 2 次超时 → 自动切 SearXNG → 当前会话不回切
```

SearXNG 是回退方案，不是主方案。ddgs 能通时优先用 ddgs（覆盖海外源）。
