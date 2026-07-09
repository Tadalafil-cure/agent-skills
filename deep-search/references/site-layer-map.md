# 站点分层速查表

> 积累自实战。已知站点直接走对应层，未知站点走完整降级链（L1→L2→L2.5→L3→L4）。
> 最后更新：2026-07-03（玻璃基板 15 篇实战）

## 直通层（L1 urllib 直接拿）

| 域名 | 典型内容 | 验证日期 |
|:--|:--|:--|
| `baijiahao.baidu.com` | 百家号自媒体 | 2026-07-02 |
| `thepaper.cn` | 澎湃新闻 | 2026-07-02 |
| `it.sohu.com` | 搜狐 IT | 2026-07-02 |
| `t.cj.sina.com.cn` | 新浪财经头条 | 2026-07-02 |
| `new.qq.com` | 腾讯新闻 | 2026-07-02 |
| `view.inews.qq.com` | 腾讯新闻快讯 | 2026-07-02 |
| `caifuhao.eastmoney.com` | 东方财富财富号 | 2026-07-02 |
| `zhuanlan.zhihu.com` | 知乎专栏 | ❌ 403 → 必须 L2.5 |
| `arxiv.org` | 学术论文 | 专用 L4 |

## 必须 Botasaurus（L2.5 bypass_cloudflare=True）

| 域名 | 原因 | 验证日期 |
|:--|:--|:--|
| `xueqiu.com` | WAF cookie 拦截，urllib 返回垃圾 | 2026-07-02 |
| `zhuanlan.zhihu.com` | 403 + 反爬验证页 | 2026-07-03 |

## 待验证（新域名走完整降级链）

| 域名 | 猜测 | 状态 |
|:--|:--|:--|
| `mp.weixin.qq.com` | 可能需要 browser_navigate | 未验证 |
| `eastmoney.com`（非 caifuhao） | 可能 L1 可行 | 未验证 |
| `research.cicc.com` | 可能需要 L2.5 | 未验证 |
| `data.eastmoney.com` | 可能 L1 可行 | 未验证 |

## 工具链就绪状态

| 层 | 工具 | 状态 | 备注 |
|:--:|:--|:--:|:--|
| L1 | urllib + re | ✅ | 主力，80% 覆盖率 |
| L2 | scrapling 0.4.9 | ✅ | `extract get` → `fetch` 两层 |
| L2.5 | Botasaurus @browser | ✅ | `--no-sandbox`, `bypass_cloudflare=True` |
| L3 | browser_navigate | ⚠️ | daemon socket 不稳定 |
| L4 | arXiv API | ✅ | 学术论文专用 |
| L5 | Firecrawl keyless | ✅ | 前 4 层全挂才用 |
| L6 | browser-act | 手动 | 询问用户 |

## 降级链铁律

```
对每个 URL：
  ┌─ 已知站点？查此表 → 直接用对应层
  └─ 未知站点？逐层试：
       L1 urllib ──失败──→ L2 scrapling get ──失败──→ L2 scrapling fetch
         │                       │                          │
         └──成功→记录到表        └──成功→记录               └──成功→记录
                                                             │
                                                           失败
                                                             ↓
                                              L2.5 Botasaurus @browser
                                              (bypass_cloudflare=True)
                                                             │
                                                           失败
                                                             ↓
                                              L3 browser_navigate
                                                             │
                                                           失败
                                                             ↓
                                              L5 Firecrawl keyless

每轮必须抓取 ≥5 篇正文。不够就继续降级。
不允许"L1 失败就跳过"。
```
