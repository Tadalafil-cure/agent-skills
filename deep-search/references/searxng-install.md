# SearXNG 安装与排障手册

> deep-search 回退后端。ddgs 被墙时的唯一搜索来源。

## 安装（Git Clone — 唯一正确方式）

**不要用 `pip install searxng`**——PyPI 包不含 `settings.yml`，装上无法运行。

```bash
# 1. 克隆到永久目录（不要放 /tmp）
git clone https://github.com/searxng/searxng /home/admin/searxng
cd /home/admin/searxng

# 2. 安装依赖（到 hermes venv）
/home/admin/.hermes/hermes-agent/venv/bin/pip3 install msgspec lxml httpx pyyaml -q

# 3. 不需要 pip install -e！直接 PYTHONPATH 运行
```

## settings.yml 四步配置

默认 `/home/admin/searxng/searx/settings.yml`（git clone 自带），**必须改四处**：

### ① 端口（默认 8888 → 8880）

```yaml
server:
  port: 8880              # 改这里
  bind_address: "127.0.0.1"
```

### ② secret_key（默认 ultrasecretkey → 随机值）

不改直接报错退出：`server.secret_key is not changed`

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# 输出填入 settings.yml
```

```yaml
server:
  secret_key: "55d0860dc5b67565cf09b1b82b6add4a5e068c7fff7c5728140ccc7dd3a93745"
```

### ③ search.formats（必须加 json）

默认只有 `html`，不加 json 会导致所有 `?format=json` 请求返回 **403 Forbidden**。

```yaml
search:
  formats:
    - html
    - json          # 必加
```

### ④ 引擎启用（默认全部 disabled）

baidu/360/sogou 三引擎必须手动改为 `disabled: false`：

```yaml
engines:
  - name: 360search
    disabled: false         # 改这里

  - name: baidu
    disabled: false         # 改这里

  - name: sogou
    disabled: false         # 改这里
```

## 启动

```bash
cd /home/admin/searxng && \
SEARXNG_SETTINGS_PATH=/home/admin/.searxng/settings.yml \
PYTHONPATH=/home/admin/searxng \
/home/admin/.hermes/hermes-agent/venv/bin/python3 searx/webapp.py
```

> 建议把 settings.yml 复制到 `/home/admin/.searxng/`（持久路径），和 git clone 源码分离。

## 健康检查

```bash
curl -s http://127.0.0.1:8880/healthz     # OK = 服务正常
curl -s "http://127.0.0.1:8880/search?format=json&q=test" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['results']))"
```

## 错误码速查

| 错误 | 原因 | 修复 |
|------|------|------|
| **403 Forbidden** | `search.formats` 缺 `json` | 加 `- json` 到 formats 列表 |
| **500 Internal Server Error** | `default_doi_resolver` 缺失 | settings.yml 版本过旧，用 git clone 自带的 |
| **server.secret_key is not changed** | 未改默认 key | 生成随机值填入 |
| **connection refused** | 进程没起或端口错 | 检查 `port: 8880`，fuser -k 旧进程 |
| **0 results / 无关结果** | 引擎 scraper 过期或查询词撞车 | 换英文查询词，避免短缩写 |

## 配置持久化

```bash
# 设置环境变量（加到 ~/.bashrc 或 deep-search 脚本）
export SEARXNG_URL=http://127.0.0.1:8880
export SEARXNG_SETTINGS_PATH=/home/admin/.searxng/settings.yml
```

## ⚠️ 禁止操作

- **禁止 `pip install --force-reinstall searxng`** — 会删除 git clone 的 `searx/` 目录
- **禁止用 PyPI pip 包** — 不含 settings.yml
- **禁止放 /tmp** — 系统可能清理
- **禁止用 sudo pip install** — 污染系统 Python
