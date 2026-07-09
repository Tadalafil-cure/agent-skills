---
name: browser-act
description: 增强浏览器自动化 —— browser-act CLI 包装器，补 Hermes 内置 browser_* 工具的短板：JS渲染抓取、网络抓包(HAR/XHR)、验证码、反爬代理、登录态持久、多会话。遇到验证墙/SPA/需要登录/需要找API时优先用此 skill。
version: 1.0.1
metadata:
  requires:
    cli: browser-act (uv tool install browser-act-cli --python 3.12)
    runtime: Python 3.12+
---

# browser-act 增强浏览器

> CLI: `browser-act` | 安装: `uv tool install browser-act-cli --python 3.12`

## 使用决策树

```
遇到网页 →
  ├─ 纯文本/API/静态页 → Hermes 内置 browser_* / curl
  ├─ JS 渲染/SPA/需要截图 → browser-act stealth-extract
  ├─ 需要登录态 → browser-act browser import-profile
  ├─ 需要找内部 API → browser-act network requests
  ├─ 验证码挡路 → browser-act solve-captcha
  ├─ 批量/重复抓 → browser-act-skill-forge 生成专用 skill
  └─ 复杂交互/表单 → browser-act session 交互模式
```

## 核心命令速查

### 快速提取（不开浏览器会话）

```bash
# JS 渲染后抓取，输出 Markdown
browser-act stealth-extract <url>

# 指定输出格式/代理/超时
browser-act stealth-extract <url> --content-type html|markdown
browser-act stealth-extract <url> --dynamic-proxy us
browser-act stealth-extract <url> --timeout 60
browser-act stealth-extract <url> --output ./result.md
```

### 交互模式（需先 open session）

```bash
# 创建/打开浏览器会话
browser-act browser create --type stealth --name "my-session" --desc "任务描述"
browser-act browser open <id> [url]

# 页面操作（--session 指定会话）
browser-act --session my-session state              # 页面快照
browser-act --session my-session navigate <url>      # 导航
browser-act --session my-session click <index>       # 点击
browser-act --session my-session input <index> <text> # 输入
browser-act --session my-session screenshot [path]   # 截图
browser-act --session my-session get markdown        # 提取MD
browser-act --session my-session eval <js>           # 执行JS
browser-act --session my-session scroll up|down      # 滚动
```

### 网络抓包

```bash
browser-act --session my-session network requests --type xhr
browser-act --session my-session network request <id>
browser-act --session my-session network har start
browser-act --session my-session network har stop [path]
```

### 登录态

```bash
browser-act browser list-profiles                    # 列 Chrome profiles
browser-act browser import-profile <browser_id> <profile_id>  # 导入登录态
```

### 验证码

```bash
browser-act --session my-session solve-captcha       # 自动处理
browser-act --session my-session remote-assist       # 需要人工时
```

### 管理

```bash
browser-act browser list                             # 列浏览器
browser-act session list                             # 列会话
browser-act browser delete <id>                      # 删浏览器
browser-act session close <name>                     # 关会话
```

## browser-act-skill-forge（网站→Skill 生成器）

对特定网站生成可复用的 Python 脚本 + SKILL.md，后续不用再开浏览器。

```bash
# 触发：加载此 skill 后，说 "对 <网站> 用 skill-forge"
# 流程：探索 → 找 API → 生成脚本 → 安装到 ~/.hermes/skills/
```

### skill-forge 适用场景

| 场景 | 示例 |
|------|------|
| 需要批量抓取 | "抓取京东 100 个商品信息" |
| 需要监控变化 | "每天检查这个页面价格" |
| 需要登录后操作 | "登录后导出数据" |
| 需要翻页/搜索 | "搜索并收集所有结果" |

## 与 Hermes 内置工具的关系

| 场景 | 首选 |
|------|------|
| 普通网页、静态内容 | Hermes `browser_*` |
| 简单 API / 文本端点 | `curl` (terminal) |
| JS 渲染、反爬、登录、验证码 | **browser-act** |
| 批量、重复、需要脚本化 | **browser-act → skill-forge** |

## ⚠️ 已知陷阱

### 微信文章（mp.weixin.qq.com）

微信公众平台有双层防护：验证码网关 + 境外代理 SSL 阻断。实测结论：

| 方式 | 结果 |
|------|------|
| `stealth-extract`（无代理） | 验证码网关拦截（Error 230404） |
| `--dynamic-proxy us` | SSL_PROTOCOL_ERROR |
| `--dynamic-proxy hk/tw/sg` | 同上，亚洲代理也被封 |

绕过方案：
1. 浏览器交互模式 `browser open` → `remote-assist` 让用户手动过验证码
2. 微信文章优先让用户直接粘贴内容，不依赖程序抓取
3. 如需批量抓微信文章，需用户本地有登录态 Chrome profile → `import-profile`

### 安装耗时

`uv tool install browser-act-cli` 下载约 140MB（opencv 60MB + numpy 16MB + 其他），国内网络需 2-3 分钟。

## 费用模型

| 层级 | 能力 | 费用 |
|------|------|:--:|
| 免费 | 本地浏览器(5 profile)、会话管理、网络抓包、表单自动化 | ¥0 |
| 付费 | 动态代理(~$3.2/GB)、验证码识别、Workflow Step(~$0.016/步) | 消耗 credits |

注册送 100 credits，GitHub OAuth 登录无需绑卡。免费能力已覆盖 Hermes 需要的全部增强点。

## 环境

- 安装: `uv tool install browser-act-cli --python 3.12`（首次约 2-3min）
- 验证: `browser-act --version`（当前 v1.0.1）
- 配 Key: `browser-act auth set <key>`（https://www.browseract.com → Settings）
- 代理区域: `browser-act proxy regions`（37 个地区）
- 状态: `browser-act browser list` / `browser-act session list`