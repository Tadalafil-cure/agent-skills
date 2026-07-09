# SearXNG 假死 vs CAPTCHA 诊断 — 2026-06-29 更新

## 现象

- `/config` 返回 HTTP 200，JSON 正常
- 所有引擎（baidu/bing/sogou）搜索返回 0 结果
- 无 error、无 unresponsive_engines——静默归零
- `curl https://www.baidu.com/s?wd=test` 返回 302（百度本身正常）

## ⚠️ 关键区分：假死 vs CAPTCHA

**两者症状完全相同**（搜索返回 0），但根因和修复完全不同：

| | 假死 | CAPTCHA |
|:--|:--|:--|
| 原因 | SearXNG 进程内部状态异常 | 百度反爬封 IP |
| SearXNG 日志 | 无相关错误 | `CAPTCHA (suspended_time=3600)` |
| `/config` | 正常 | 正常 |
| 百度直连 | 正常（302） | 正常（302） |
| 修复 | 重启 SearXNG | **等 suspended_time 过期** |
| 重启有用？ | ✅ 秒恢复 | ❌ 无效——CAPTCHA 是 IP 级别 |

### 诊断命令（必跑）

```bash
# ① 检查进程
ps aux | grep searx.webapp | grep -v grep

# ② 测试搜索（不是 config）
curl -s "http://127.0.0.1:8880/search?q=test&engines=baidu&format=json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('results',[])))"

# ③ 对比百度直连
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://www.baidu.com/s?wd=test"

# ④ ⚠️ 查看 SearXNG 日志中是否含 CAPTCHA（关键区分步骤）
# 日志路径: SearXNG 的 stderr（如果是后台运行，用 process log 查看）
# 含 "CAPTCHA (suspended_time=..." → 不是假死，等过期
# 不含 → 可能是假死，重启
```

## 修复

```bash
# 仅假死时使用。CAPTCHA 时重启无效。
pkill -f "searx.webapp"
sleep 2
cd /home/admin/searxng && SEARXNG_SETTINGS_PATH=/home/admin/.searxng/settings.yml python3 -m searx.webapp &
sleep 8
# 验证
curl -s "http://127.0.0.1:8880/search?q=test&engines=baidu&format=json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('results',[])))"
```

## 触发条件

**CAPTCHA 触发模式**（2026-06-29 实测）：
- 6 次 Baidu 请求在 72 秒内 → 触发 CAPTCHA（suspended_time=3600s）
- a-team collect_web_search.py 的 3×12s 间隔模式会稳定触发
- 建议间隔 ≥25s，总轮次 ≤4

## 关键教训

1. **`/config` 返回 200 ≠ 搜索正常。** 必须用搜索测试验证
2. **搜索返回 0 不一定是假死。** 先查日志排除 CAPTCHA
3. **重启 SearXNG 不能绕过 CAPTCHA。** CAPTCHA 是百度 IP 级别的封禁
