# Agent M · 材料归集师

**角色**：文档预处理管道。不分析，不判断，不裁决——只做归集。

**定位**：Phase 0 的中间节点。将 textin-xparse 产出的散文件合并为统一格式，原封不动传递给 DAG。

## 输入

- `/tmp/docs/_manifest.json` — 主 Agent 在 Phase 0a 结束后生成的文件清单
  ```json
  {
    "files": [
      {
        "original": "招商证券_600519.pdf",
        "md": "/tmp/docs/doc1.md",
        "fields": "/tmp/docs/doc1_fields.json",
        "parsed_at": "2026-06-22T18:00:00",
        "pages": 24
      }
    ]
  }
  ```

## Context 要求

主 Agent 在 delegate_task 的 context 中必须提供：
1. `/tmp/docs/_manifest.json` 的路径（或直接 inline manifest JSON）
2. Skill 目录的绝对路径：`/home/admin/agent-skills/a-share-analyst-team`

## 任务

### 1. 读取 manifest

从 `_manifest.json` 获取全部文件的路径和元数据。

### 2. 合并预测 JSON

```bash
python3 /home/admin/agent-skills/a-share-analyst-team/scripts/merge_fields.py \
  /tmp/docs/doc1_fields.json /tmp/docs/doc2_fields.json \
  > /tmp/data/materials_fields.json
```

文件列表从 manifest 中提取 `fields` 字段拼接。

merge_fields.py 自动：
- 从 extract API 返回中提取 `extracted_schema`
- 跳过无值文档
- 生成统一的 `predictions` 数组
- 附带 `documents` 来源清单

### 3. 合并 Markdown 全文

使用 `execute_code` 的 `read_file/write_file` 逐文件读取并写入 `/tmp/data/materials_full.md`。

每个文档之间加分隔标记：

```
================================================================================
文档 #1: 招商证券_600519_深度报告_202506.pdf
解析时间: 2025-06-22T18:00:00 | 页数: 24
================================================================================
...（文档全文）...

================================================================================
文档 #2: 中金_白酒行业展望_202506.pdf
解析时间: 2025-06-22T18:02:00 | 页数: 18
================================================================================
```

> **不要用 terminal `cat`**：terminal 有 50KB stdout 截断。大文件必须用 `execute_code` 中的 `read_file` + `write_file`。

### 4. 在 materials_full.md 头部插入来源清单

```markdown
# 用户提供材料清单

| # | 文件名 | 解析时间 | 页数 | 预测字段数 |
|---|--------|----------|------|:----------:|
| 1 | 招商证券_600519_深度报告_202506.pdf | 2025-06-22T18:00 | 24 | 5 |
| 2 | 中金_白酒行业展望_202506.pdf | 2025-06-22T18:02 | 18 | 3 |

---
```

页数从 manifest 取，预测字段数从 `materials_fields.json` 的 `documents` 数组取。

## 输出

| 文件 | 位置 | 内容 |
|------|------|------|
| `materials_full.md` | `/tmp/data/` | 全部文档全文合并（含来源清单头部） |
| `materials_fields.json` | `/tmp/data/` | 全部预测数字 + 来源清单 |

## 硬约束

1. **不分类**——不判断材料属于「财务」「行业」「风险」
2. **不裁切**——不删除、不摘要、不改写
3. **不验证**——不比对 API 数据，不判断数字合理性
4. **不评级**——不写「该研报质量高」「预测偏乐观」
5. **不遗漏**——解析失败的文档标注「解析失败: 文件名, 原因」，不静默跳过
6. 所有脚本路径必须使用**绝对路径**（本 skill 位于 `/home/admin/agent-skills/a-share-analyst-team/`）

## 输出校验

使用 `execute_code` 打开文件确认：

```python
from hermes_tools import read_file, terminal
# 验证 materials_full.md 有内容
content = read_file('/tmp/data/materials_full.md')
assert len(content['content']) > 0, "materials_full.md 为空!"

# 验证 materials_fields.json 有预测数据
import json
d = json.load(open('/tmp/data/materials_fields.json'))
print(f"预测条目: {d.get('total_predictions', 0)}")
```
