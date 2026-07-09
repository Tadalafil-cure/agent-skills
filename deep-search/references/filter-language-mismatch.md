# 过滤器中英错配问题

**v3.1 已知问题，待修复。**

## 症状

翻译后搜索词是英文（如 "Microchannel heat dissipation"），但 SearXNG（360search）返回的结果标题/摘要为中文。
`filter_results()` 用原始中文 query 分词（"微通"/"通道"/"道散"/"散热"）去匹配中文结果，理论上能命中——
但实际 `_tokenize_query()` 用的是**翻译后的英文词**作为 query tokens，导致中文结果全部低分被误杀。

## 复现

```
输入："微通道散热"
翻译："Microchannel heat dissipation"
搜索计划 Round 1: "Microchannel heat dissipation definition overview what is"
SearXNG 返回 5 条（全部中文标题）
filter_results(query="微通道散热", ...)
  query_tokens = {"微通", "通道", "道散", "散热", "微通道散热"}  ← 原中文
  text_tokens = _tokenize_query(title)  ← 中文标题 2-gram
  部分命中（"微通"/"通道"在标题中）
  实际结果：5 条 → 保留 1 条，移除 4 条
```

## 根因

`filter_results()` 用的是外层传入的 `query`（原始中文），但 `build_search_plan()` 内翻译后的 `search_kw` 未传入过滤阶段。
`main()` 调用 `filter_results(results, query)` 时传的是原始中文，所以**理论上应该能匹配**。

但问题出在另一处：当 SearXNG 结果标题不含"微通道"等词时（如"流动沸腾冷却技术"），中文 2-gram 全部落空。

## 修复方向

1. **双语分词**：过滤时间时用原词（中文）和译词（英文）生成 tokens
2. **降低阈值**：当前 0.15 对中文 2-gram 过于苛刻（5 个 2-gram 需至少 1 个命中才能保留）
3. **直接传 search_kw**到过滤阶段，与中文结果做交叉匹配

## 暂不修复原因

当前 360search 实际召回极弱（6 轮仅 1 轮有结果），过滤误杀影响面小。
优先修 SearXNG 引擎可用性，再修过滤器。
