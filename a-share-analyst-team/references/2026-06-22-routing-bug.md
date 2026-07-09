# 2026-06-22 路由投送漏缺 Bug

## 现象

世运电路(603920)任务中，Agent F1/F2 的报告中未引用用户提供的研报材料（中邮证券 2026-04-28 PDF），尽管 routing.json 明确标记 `"F1": true, "F2": true`。

## 根因

**Phase 0d 执行时，主 Agent 手工编排 delegate_task context，在 F1/F2 的调用中遗漏了 doc1.md 和 doc1_tables.json 路径。**

routing.json 本身正确——Agent R 审阅无误，路由表内容正确。问题出在「读取 routing.json → 翻译为 Agent context」这一步的手工操作环节。

主 Agent 的操作时序：
1. ✅ read_file routing.json（确认内容正确）
2. ⚠️ 手工为每个 Agent 写 delegate_task goal/context
3. ⚠️ F1 的 context 列出了 12 份上游报告路径，但漏写 doc1.md
4. ⚠️ F2 的 context 同样漏写
5. ✅ delegate_task 派发（未做 pre-flight 校验）

## 影响

- F1 v1 未引用研报中的分析师预测作为「市场共识」的证据
- F2 v1 未直接攻击研报中的乐观论据
- 论证质量下降约 15-20%，但不改变结论方向（F1 仍然胜出）
- 其他 Agent（B1/B2/B3/P/F/I/H）均正确收到并引用了研报

## 修复

1. **立即**：补跑 F1/F2 v2，完整引用研报（已完成）
2. **流程**：SKILL.md Phase 0d 新增「分发前强制校验」步骤（v0.4.1）
3. **校验逻辑**：派发前机械核对每个 Agent 的 context 是否包含 routing 要求的全部 doc 路径

## 校验模板

```python
# 主 Agent 在 delegate_task 前应执行：
import json
routing = json.load(open(f'{TASK_BASE}/data/routing.json'))
S_routed = set()
for doc in routing['documents']:
    for agent_id, val in doc['routing'].items():
        if val:
            S_routed.add(agent_id)

# 对 S_routed 中每个 Agent，检查其 context 文本包含所有 md_path 和 tables_path
for agent_id in S_routed:
    context = agent_contexts[agent_id]  # 已编排的 context 文本
    for doc in routing['documents']:
        if doc['routing'].get(agent_id):
            assert doc['md_path'] in context, f'{agent_id} missing {doc["md_path"]}'
            assert doc['tables_path'] in context, f'{agent_id} missing {doc["tables_path"]}'
```

## 日期

2026-06-22
