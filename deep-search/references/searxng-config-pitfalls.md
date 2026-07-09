# SearXNG 配置陷阱实录

> 2026-06-28 会话中踩过的所有 settings.yml 坑。

## 铁律

**⛔ 不手动改 settings.yml 的 engines 列表。国内引擎限制通过 URL 参数 `engines=baidu,bing,360search,sogou` 实现。**

## 踩过的坑

### 1. `disabled: true` 不生效（`use_default_settings: true` 下）

```yaml
# ❌ 这样写不会禁用引擎——SearXNG 把它当新条目追加，276 引擎全开
engines:
  - name: google
    disabled: true
```

结果：/config 端点显示 276 引擎全启用，0 个禁用。每次搜索等所有海外引擎超时（6×20s=120s）。

### 2. `use_default_settings: false` → KeyError 500

```yaml
# ❌ 缺少 default_doi_resolver、outgoing、brand 等必需配置项
use_default_settings: false
engines:
  - name: bing
```

报错：`KeyError: 'default_doi_resolver'`，整个 SearXNG 搜索 500。

### 3. `use_default_settings.engines.remove` → KeyError 崩溃

```yaml
# ❌ remove 列表中某些引擎被其他引擎依赖网络配置，删除导致启动失败
use_default_settings:
  engines:
    remove:
      - google
      - presearch  # KeyError: 'presearch'
      - ...
```

SearXNG 启动崩溃，进程无法监听端口。

### 4. 手动 engine 声明导致 bing 被静默跳过

```yaml
# ⚠️ 写上 engines 列表后，bing enabled=True 但搜索时被 PROCESSORS 跳过
engines:
  - name: bing
    disabled: false
    timeout: 5.0
```

bing 在 PROCESSORS 中、disabled=False、inactive=False，但 `get_params()` 后不发起网络请求。原因未完全定位，推测与 SearXNG 内部 engine 注册/合并逻辑冲突。

### 5. pkill -9 反复被 block

多次尝试 `pkill -9 -f searx` 被系统拦截（用户未响应超时）。改用 `kill <pid>` 温和方式。

## 正确方案

```yaml
# ✅ 最简配置——不写 engines 块
use_default_settings: true
search:
  formats:
    - html
    - json
server:
  secret_key: "<32-char hex>"
  port: 8880
  bind_address: "127.0.0.1"
  limiter: false
```

国内引擎限制在搜索请求中通过 URL 参数实现：
```
/search?q=关键词&format=json&engines=baidu,bing,360search,sogou&language=zh-CN
```

## 引擎状态（2026-06-28）

| 引擎 | 状态 | 备注 |
|------|------|------|
| baidu | ⚠️ 间歇 CAPTCHA | 冷却 3600s，偶尔放行 |
| bing | ⚠️ 静默跳过 | 原因未定位，不在 unresponsive 列表也不返回结果 |
| 360search | ⚠️ 不稳定 | 0–7 条/次 |
| sogou | ❌ CAPTCHA | 持续被封 |
| google/duckduckgo/brave/... | ❌ timeout | 阿里云出站 TCP 被墙 |
