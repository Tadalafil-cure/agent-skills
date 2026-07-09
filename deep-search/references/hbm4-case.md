# HBM4 v1.6 协议实测案例

> 2026-06-28 · 4 轮搜索 · 12 次抓取 · 12/12 全文（含 browser-act 补抓）

## 协议执行

### 维度覆盖路径

| 轮次 | 查询词 | 命中 | 覆盖维度 |
|:--:|------|:--:|------|
| 1 | `HBM4 memory 2026` | 8 | 定义、原理 |
| 2 | `Samsung SK Hynix HBM4 competition` | 8 | 产业链、竞争 |
| 3 | `HBM4 advanced packaging TSMC CoWoS` | 6 | 原理（封装） |
| 4 | `NVIDIA Vera Rubin HBM4 production timeline` | 6 | 应用、进展 |

第 4 轮后六维全覆，达标终止。

### 流水线抓取数据

| 层 | 工具 | 成功 | 失败 |
|:--:|------|:--:|:--:|
| L1 | scrapling get | 10/12 | Intel 181B, Chosun 78B |
| L2 | scrapling fetch (自动) | 1/2 | Intel→29.7KB ✅, Chosun 超时 |
| — | 终报时 | 11/12 (92%) | Chosun 待抓取 |
| L3 | browser-act (用户确认后) | 1/1 | Chosun→13.6KB ✅ |
| — | 最终 | **12/12 (100%)** | — |

### browser-act 确认激活流程（v1.6 新增）

```
终报输出 + 待抓取清单:
  ⚠️ 1 条未成功: biz.chosun.com (get 78B / fetch 超时)
  询问用户 → 用户明示同意 → 启动 Chromium → browser-act → 13.6KB ✅
```

### 每轮展示格式陷阱

HBM4 第一遍执行时，Agent 将每轮 8 条结果压缩为 "8 条命中——三星率先通过验证" 一行简报。
用户反馈"搜索结果没反馈给我"。v1.6 已加 ⛔ 格式陷阱：每轮必须逐条列出标题+来源（至少前 3 条）。

## 关键数据产出

- 4 轮 ddgs 搜索 → 28 条原始结果
- 12 次后台 scrapling 启动（与搜索并行）
- 11 篇 Layer 1+2 抓取 + 1 篇 browser-act 补抓 = 12/12
- 3 篇深度分析：Aju Press 11KB, SpoonAI 15KB, AI in Asia 24KB

## 踩坑记录

1. **纯英文长词超时**：`HBM4 Samsung NVIDIA Rubin 2026` → TimeoutException → 换 `HBM4 memory 2026` 成功
2. **文件锁自动等待**：R2→R3 间隔 14.1s，锁自动补等 5.9s → 达 20s
3. **Chosun 反爬三层全路径**：get 78B → fetch 超时 → browser-act 13.6KB（验证三层兜底完整）
4. **browser-act 需要 Chromium 后台**：首次调用失败（无 Chrome 实例），后启动 `/home/admin/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome --headless --no-sandbox --disable-gpu --remote-debugging-port=43209` 后成功
5. **ddgs 后续全面宕机**：同一天稍晚测试玻璃基板时，ddgs 所有查询全超时（含 `"test"`），Google/Brave 后端从该服务器不可达。v1.6 已加入宕机应对规则：3 次连续超时→告知用户→不循环重试
