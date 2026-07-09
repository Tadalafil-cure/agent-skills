---
name: textin-xparse
description: >
  TextIn xParse 智能文档解析 + 抽取 + 票据识别 —— 同一 API Key 覆盖三能力。
  解析（文档→Markdown/JSON）、抽取（按 JSON Schema 提取字段）、票据（20+种票据自动识别）。
  当用户需要解析文档、OCR、文档转 Markdown、按字段抽取信息、识别发票/车票时使用本技能。
version: 1.2.1
platforms: [linux]
metadata:
  hermes:
    tags: [document, ocr, parsing, extraction, invoice, bill, markdown, pdf, rag, llm]
    skill_dir: /home/admin/agent-skills/textin-xparse
---

# TextIn xParse — 解析 + 抽取 + 票据

一个 API Key 覆盖三种能力：

| 能力 | 做什么 | 输入 | 配置 |
|------|--------|------|:--:|
| **解析 (Parse)** | 文档→Markdown+JSON | 文档文件/URL | 无需 |
| **抽取 (Extract)** | 按 Schema 提取字段 | 文档 + JSON Schema | Schema |
| **票据 (Bill)** | 自动识别 20+ 种票据 | 票据图片/URL | **零配置** |

## 环境信息

| 项目 | 值 |
|------|-----|
| 技能目录 | `/home/admin/agent-skills/textin-xparse` |
| 解析脚本 | `python3 /home/admin/agent-skills/textin-xparse/scripts/parse.py` |
| 配置文件 | `config.json`（含 app_id / secret_code） |

## 命令一览

```bash
# === 解析 ===
python3 parse.py sync <文件>              # 同步解析，直接返结果
python3 parse.py sync <文件> --json       # + 完整 JSON
python3 parse.py async <文件>             # 异步提交+轮询等结果
python3 parse.py async <文件> --no-wait   # 仅提交，返回 task_id
python3 parse.py result <task_id>         # 查询异步结果
python3 parse.py download <image_url>     # 下载解析出的图片

# === 抽取 ===
python3 parse.py extract <file> --schema '{"type":"object","properties":{...}}'
python3 parse.py extract <file> --schema-file schema.json
python3 parse.py extract <file> --schema '...' --page-start 1 --page-count 3
python3 parse.py extract <file> --schema '...' --json  # 完整 JSON

# === 票据识别 ===
python3 parse.py bill <file>               # 自动识别票据类型+字段
python3 parse.py bill <file> --json        # + 完整 JSON
python3 parse.py bill <file> --crop-images --crop-fields  # + 裁切图
python3 parse.py bill <file> --merge-digital   # 合并多页数电票
python3 parse.py bill <file> --pages 1,3-5     # 指定页码
```

## 票据识别（零配置）

扔一张票据图片进去，自动识别类型并提取所有标准字段。支持 20+ 种中国票据：

| 类型 | 说明 |
|------|------|
| 增值税发票 | 增值税专用/普通发票 |
| 数电票 | 数字化电子发票 |
| 火车票 | 铁路电子客票/纸质票 |
| 航空运输电子客票 | 行程单 |
| 出租车票 | 出租车发票 |
| 定额发票 | 通用定额发票 |
| 网约车行程单 | 网约车电子发票 |
| 过路过桥费发票 | 车辆通行费 |
| 二手车销售发票 | 二手车交易发票 |
| 机动车销售发票 | 机动车销售统一发票 |
| 增值税销货清单 | 销货明细 |
| 通用机打发票 | 机打票据 |
| 公路/船运/停车票 | 客运/运输发票 |
| 医疗发票 | 电子/纸质门诊/住院发票 |
| 非税收入统一票据 | 行政事业票据 |

每条票据自动提取的字段因类型而异（发票号码、金额、税额、日期、购销方等），无需写 Schema。

## 抽取 Schema 示例

```json
{
  "type": "object",
  "properties": {
    "发票号码": {"type": "string", "description": "发票编号"},
    "开票日期": {"type": "string", "description": "开票日期"},
    "金额": {"type": "number", "description": "发票总金额"},
    "明细": {
      "type": "array",
      "description": "发票明细列表",
      "items": {
        "type": "object",
        "properties": {
          "名称": {"type": "string", "description": "商品名称"},
          "数量": {"type": "integer", "description": "数量"},
          "单价": {"type": "number", "description": "单价"}
        }
      }
    }
  }
}
```

⚠️ **V3 抽取 API 不支持 `required` 字段**（任何层级、任何内容都会触发 40004）。字段的可选/必选由 API 自行判断，不要写 `required`。每个字段标注 `"type": ["string", "null"]` 即可让该字段成为可选。

支持的字段类型：`string`, `number`, `integer`, `enum`, `object`, `array`
支持嵌套，最大 3 级，叶子节点不超过 100 个。

## 抽取结果格式

```json
{
  "code": 200,
  "data": {
    "result": {
      "extracted_schema": {
        "发票号码": "12345678",
        "金额": 1000.00
      },
      "citations": {
        "发票号码": {
          "value": "12345678",
          "bounding_regions": [...],
          "llm_confidence": 0.98,
          "llm_confidence_level": "high"
        }
      },
      "usage": {"acgpt_total_tokens": 1297}
    }
  }
}
```

每个字段带置信度（high/medium/low）和坐标溯源。

## 支持的输入格式

PDF、Word (.doc/.docx)、Excel (.xls/.xlsx)、PPT (.ppt/.pptx)、
图片 (.png/.jpg/.jpeg/.bmp/.tiff/.webp)、HTML、TXT、OFD
支持本地文件或 HTTP URL。

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/xparse/parse/sync` | POST | 同步解析 |
| `/api/v1/xparse/parse/async` | POST | 异步解析 |
| `/api/v1/xparse/parse/async/{id}` | GET | 查异步结果 |
| `/ai/service/v3/entity_extraction` | POST | 字段抽取 (JSON body) |
| `/ai/service/v1/bill_recognize_v2` | POST | 票据识别 (raw binary) |

## 使用场景

- 扫描件/PDF → Markdown 供 LLM 理解
- RAG 知识库文档预处理
- 财报/合同/票据的表格提取
- **发票/合同/订单的字段自动抽取**（新增）
- **批量文档关键信息提取**（新增）
- Agent 工具链中的文档解析/抽取节点

## 限制

- 同步接口有超时，大文件用异步
- 单文件建议 < 100MB
- 抽取叶子节点 ≤ 100 个，嵌套 ≤ 3 级
