# Bing cn 纯中文查询崩溃实录

*2026-06-28 · SearXNG via cn.bing.com · deep-search v1.10 收录*

## 现象

Bing cn 引擎对**纯中文技术查询**返回内容与查询词完全无关。不是结果质量差，而是**内容完全随机**——搜索引擎似乎在忽略查询词，返回当下热搜/缓存内容。

## 实测案例

| 查询词 | 返回内容 | 来源引擎 |
|--------|---------|---------|
| `microchannel heat sink 原理` | 葡萄牙 0-0 哥伦比亚（世界杯新闻） | bing |
| `微通道 散热 原理` | 巨人柱仙人掌百科（10 条全是） | bing |
| `微通道换热器 液冷 数据中心` | 百度首页、百度下载链接 | bing |
| `MLCP NVIDIA microchannel liquid cooling` | 抖音商品卡教程 | bing |
| `液冷板 微通道`（30 分钟后重试） | 雷诺股票行情 RNO | bing |
| `microchannel cooling heat transfer` | 披萨馅料种类、手抛披萨 | bing |
| `微通道散热 芯片` | QQ 邮箱设置教程 | bing |
| `微通道 液冷板 MLCP` | 哔哩哔哩倍速播放问题 | bing |
| `cold plate liquid cooling vs` | 0 条相关 | bing |
| `中国 经济` | 微生物培养基配方 | bing |
| `test` | 单词 test 的词典释义（勉强算"相关"） | bing |

## 有效模式——英文技术词

换用**英文技术词为主**后，Bing cn 恢复正常质量：

| 查询词 | 返回 | 质量 |
|--------|:--:|------|
| `microchannel heat sink cooling technology` | 6 条学术论文 | ✅ 高质量 |
| `microchannel liquid cooling data center` | 5 条相关 | ✅ |
| `MLCP microchannel cold plate NVIDIA` | 6 条（含雪球产业链） | ✅ |
| `microchannel heat exchanger design` | 5 条（含 Danfoss） | ✅ |
| `微通道 散热器 液冷板 原理` | 4 条（中英混合可用） | ✅ |

> ⚠️ **2026-06-28 更新**：上述有效模式是通过 **SearXNG 的 Bing 连接器** 测得的（SearXNG 会给 Bing 请求附加完整的浏览器级 headers）。直接用 `urllib` / `curl` 发送英文查询时，Bing cn 仍可能返回垃圾（如 "microchannel cooling thermal management" → 抖音商品卡）。**结论：Bing cn 的结果质量高度依赖请求 headers**，裸 urllib 不如 SearXNG 的完整 headers。

## 结论

1. **Bing cn 对纯中文技术查询（≥3 字）完全不可用**——搜索引擎可能是用中文词先做分词再翻译为英文搜索，过程中丢失语义
2. **英文技术词查询正常**——Bing cn 的英文搜索能力未受影响
3. **中英混合（中文 ≤2 词 + 英文）有时可用**——取决于中文词的歧义程度
4. **搜索引擎本身没有宕机**——每次都能返回结果，只是结果错误

## 搜索策略铁律

```
纯中文词 → ❌ 禁止（返回垃圾）
英文技术词 → ✅ 首选
中英混合短词 → ⚠️ 备选（中文词 ≤2 字）
```

搜索时**第一条查询就应使用英文技术词**——不要在纯中文查询上浪费轮次。
