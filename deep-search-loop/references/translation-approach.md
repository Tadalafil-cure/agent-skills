# 中文→英文翻译方案选型

**结论：用 `translate` 包（MyMemory 后端），不用 `deep-translator`（Google）。**

## 背景

SearXNG 国内引擎对纯中文查询召回极弱（百度/搜狗 CAPTCHA，Bing 静默跳过，仅 360search 偶尔工作）。实测发现英文查询词命中率显著更高。

## 测试对比

| 包 | 后端 | 国内可达 | 速度 | 质量 |
|---|------|----------|------|------|
| `deep-translator` (GoogleTranslator) | translate.google.com | ❌ TCP 被墙，30s timeout | — | — |
| `translate` | MyMemory API | ✅ | <5s | 技术词准确 |

## 安装

```bash
pip install translate
```

## 调用

```python
from translate import Translator
result = Translator(to_lang='en', from_lang='zh').translate('微通道散热')
# → 'Microchannel heat dissipation'
```

## 翻译质量

| 中文 | 英文 | 可用 |
|------|------|:--:|
| 微通道散热 | Microchannel heat dissipation | ✅ |
| 液冷服务器 | Liquid Cooling Server | ✅ |
| 玻璃基板 | Glass substrate | ✅ |
| HBM4 内存 | HBM4 memory | ✅ |

> 注："microchannel heat dissipation" 不如 "microchannel cooling" 自然，但搜索结果可用。

## 回退

翻译失败时保留原词，产生中英混合查询（如 "微通道散热 definition overview what is"）。
实测混合查询在 360search 上仍有一定命中率（6 条），优于纯中文（0 条）。

## 坑

- `translate` 包依赖 `requests`，需网络访问 `api.mymemory.translated.net`
- 调用超时设 10s，避免阻塞主流程
- 首次调用可能较慢（DNS + 连接建立）
