---
name: a-share-analyst-team
description: A 股深度分析引擎 —— 20 Agent 辩论架构 + ST 风险预警 + 外部材料接入，从市场全景到个股投资论文的完整分析链。输入股票代码 + 可选研报/文档材料，产出 multi-agent 协作分析报告。
trigger: 用户请求对某只 A 股做「深度分析/全面分析/投资分析/辩论分析」时加载。用户带附件时自动触发 Phase 0 文档预处理。
tags: [a-share, analysis, multi-agent, debate, risk, document]
version: 0.9.0
---
# a-share-analyst-team · A 股深度分析引擎

> v0.9.0（双引擎 + 去中心化）：F#11 搜索升级为 Firecrawl（主力）+ Baidu（补中文）双引擎并行。Step 0 从 6 轮 ddgs 缩为 3 轮流水线（≥30s/轮，边搜边抽）。子 Agent 可按需自搜（ddgs_safe.py v3.0）。
> v0.8.7：多元思维模型五大约束嵌入（贝叶斯更新/价格弹性/产能兑现率/Lollapalooza对等/基本面估值止损）+ H方法论审计第四路
> v0.8.6：web_search 通用能力（F#11前置+自主搜索）+ 多源交叉验证置信跃升 + 周线分析强制 + 系统性偏空修正
> 版本：v0.8.1 | 状态：G→A合并（A1/A2/A3即宏观策略层）。S板块分析师新增。P1/P2/P3 ⏸️TBD。D/S并行Step4。闭环Step4→F
> v0.5.1：F 报告结构校验 + 输入格式统一
> v0.5: 因子质量注入（factor-quality 前置模块 → C1/C2/E Agent 按桶获取有效因子）；大指数分批拉K线（每批100只不掉数据）；面板文件带时间戳（_meta.json 索引历史版本）
> v0.4 重构：Phase 0 四步架构（解析→提取→审阅→精准分发）；TextIn extract 下线，改为 Python 表提取；Agent R 审阅+路由；全量广播→精准分发
> v0.4.1 加固：Phase 0d 分发前强制校验（防漏投送）+ E brief 脚本输出落盘约束 + I brief 文件存在性校验 + I Agent 重算排序陷阱
> v0.3.1 新增：硬约束 #5 脚本现场执行、#6 脚本输出即铁证、#7 规模排名全量分母
> v0.2 新增：ST 风险预警（R1-R4 + E1-E3）、新浪处罚爬虫、结构化输出模板、DAG 工作流
> 位置：`~/.hermes/skills/a-share-analyst-team/`

## 触发条件

当用户请求以下任一操作时，主 Agent 必须加载此 skill：
- 「分析 XXX」（XXX 为 A 股代码或名称）
- 「深度分析/全面分析/辩论分析 某股票」
- 「帮我看看 600519」
- 任何涉及「多维度分析 + 投资决策」的 A 股个股分析请求
- **用户消息含文件附件（PDF/图片）→ 自动触发 Phase 0 文档预处理**

## Phase 0：外部材料接入（v0.4 重构）

> 用户提供研报/文档时，每份文档独立处理：解析 → 提取 → 审阅 → 精准分发。
> 不合并、不拼接——每份文档保留完整溯源链。

### 触发条件

- 用户消息含文件附件（PDF/图片）
- 用户说「附上材料」「以下是我收集的资料」等
- 用户消息中含 URL 指向研报/文档

### 流程

```
Phase 0a: 文档解析（主 Agent 执行，每份文档并行）
  full_parse.py     → docs/doc1.md, docs/doc2.md, ...
  （全量 Markdown，不做截断）
                    │
                    ↓
Phase 0b: 表格提取（主 Agent 执行，每份文档独立）
  table_extract.py  → data/doc1_tables.json, data/doc2_tables.json, ...
  （五张财务预测表，金额归一万元）
                    │
                    ↓
Phase 0c: 内容审阅 (Agent R)
  读全部 docs/doc*.md → 逐份判断内容类型 → 产路由表
  → data/routing.json（含 N 条文档，每条独立路由）
  **只判类型，不判质量**
                    │
                    ↓
Phase 0d: 精准分发（主 Agent 执行）
  读 routing.json → 按文档路由为每个 Agent 注入文件路径列表
  → B1 context: "材料: docs/doc1.md, data/doc1_tables.json"
  → C1 context: "材料: （无）"（不含技术分析，不投送）
  ⚠️ Phase 0 与 Step 0 可并行启动；
     Step 1 启动前 Phase 0 必须完成即可
```

### Phase 0a：文档解析

```bash
TASK_BASE=/tmp/{symbol}_{date}
mkdir -p $TASK_BASE/docs $TASK_BASE/data $TASK_BASE/reports $TASK_BASE/data/scripts_output

# 每份文档独立产出全量 MD（可并行）
python3 /home/admin/agent-skills/a-share-analyst-team/scripts/full_parse.py 研报A.pdf \
  > $TASK_BASE/docs/doc1.md
python3 /home/admin/agent-skills/a-share-analyst-team/scripts/full_parse.py 产品手册.pdf \
  > $TASK_BASE/docs/doc2.md
```

> `full_parse.py` 内部调 TextIn parse API，直接取 `markdown` 字段全文（不经过 3000 字符截断）。

### Phase 0b：表格提取

```bash
# 每份文档独立提取（可并行）
python3 /home/admin/agent-skills/a-share-analyst-team/scripts/table_extract.py \
  $TASK_BASE/docs/doc1.md \
  > $TASK_BASE/data/doc1_tables.json

python3 /home/admin/agent-skills/a-share-analyst-team/scripts/table_extract.py \
  $TASK_BASE/docs/doc2.md \
  > $TASK_BASE/data/doc2_tables.json
```

> `docN_tables.json` 为空（无财务表格）是合法输出，Agent R 会据此判定不含财务预测。

提取五张财务预测表（如 MD 包含的话）：

| 表名 | key | 说明 |
|------|-----|------|
| 预测指标简表 | `core` | 分析师核心观点（营收/净利/EPS/增速/PE） |
| 资产负债表 | `balance` | 支撑式猜想 |
| 利润表 | `income` | 支撑式猜想 |
| 现金流量表 | `cashflow` | 支撑式猜想 |
| 主要财务指标 | `metrics` | 衍生计算（毛利率/净利率/ROE/周转率/PE/PB/PS） |

金额统一归一为**万元**。百分比和每股数据保留原值。

### Phase 0c：内容审阅（Agent R）

Agent R 接收所有 `docs/doc*.md` 和 `data/doc*_tables.json` 的路径列表，逐份审阅每份文档含什么内容，产出多文档路由表。

详见 `references/agent-r-brief.md`。

### routing.json 格式（多文档）

```json
{
  "task": "{symbol}_{date}",
  "documents": [
    {
      "file": "华鑫证券_泛亚微透.pdf",
      "md_path": "docs/doc1.md",
      "tables_path": "data/doc1_tables.json",
      "content_inventory": {"财务预测": true, "技术分析": false, ...},
      "routing": {"B1": true, "B2": true, "C1": false, ...}
    },
    {
      "file": "产品手册_CMD.pdf",
      "md_path": "docs/doc2.md",
      "tables_path": "data/doc2_tables.json",
      "content_inventory": {"财务预测": false, "技术分析": true, ...},
      "routing": {"B1": false, "C1": true, ...}
    }
  ]
}
```

### Phase 0d：精准分发

主 Agent 读取 `routing.json`，对每个下游 Agent 计算应接收的文档列表：

```
for each Agent ID:
  docs = [d for d in routing.documents if d.routing[Agent ID] == true]
  context 注入:
    "材料文件: d[0].md_path, d[0].tables_path, d[1].md_path, ..."
```

**⛔ 分发前强制校验（v0.4.1 新增——防漏投送）**：

在派发任何 Agent 之前，主 Agent 必须执行以下机械校验。不通过 → 不得派发。

```
1. 从 routing.json 读出全部 Agent ID → 得到应接收材料的 Agent 集合 S_routed
2. 从已编排的 delegate_task 列表中提取每个 Agent 的 context 文本
3. 对 S_routed 中每个 Agent：
   - 检查 context 中是否包含所有 docs/docN.md 路径
   - 检查 context 中是否包含所有 data/docN_tables.json 路径
   - 缺失 → 🔴 阻断，补齐后重验
4. 对不在 S_routed 中的 Agent：
   - 检查 context 中是否误含 doc 路径
   - 误含 → 🟡 警告（跨路由泄漏）
```

> **已踩坑**：2026-06-22 世运电路(603920)任务中，F1/F2 routing=true 但主 Agent 手工编排 context 时漏写 doc 路径，导致 F1/F2 未引用研报。此校验步骤即为此类漏投送而设。参见 `references/2026-06-22-routing-bug.md`。

**核心纪律**：
- C1/C2/C3 只收含技术分析的文档。不含时，`docs` 列表为空，不注入任何材料路径
- 每个文档独立溯源：Agent 引用时必须标注文件名 + 段落位置
- **不合并、不拼接**——每份文档保持独立文件
- **校验必须先于派发**——编排完所有 Agent context 后、delegate_task 调用前，执行校验

> 退役文件名：~~materials_full.md~~  ~~materials_tables.json~~  ~~materials_fields.json~~  ~~_manifest.json~~。所有材料文件均以 `docs/docN.md` + `data/docN_tables.json` 形式存在。

### 🆕 F#11 网络搜索模块（v0.9 · 双引擎 + 去中心化）

> 在 Step 0 S1 阶段并行运行。脚本 `scripts/collect_web_search.py`（v3.0）。
> Step 0 只做 **3 轮初始采集**，子 Agent（B1/B2/S/F1/F2）可通过 `scripts/ddgs_safe.py`（v3.0）**自主补充搜索**。

#### 架构（v0.9）

| 维度 | 说明 |
|:--|:--|
| **搜索引擎** | Firecrawl keyless（主力）+ SearXNG/Baidu（补中文），每轮双引擎并行 |
| **轮次** | **3 轮**（R1 个股概况 → R2 行业全貌 → R3 多空观点），**所有 Agent 的共同地图**。各 Agent 以此为基线，按需自搜深挖 |
| **间隔** | **≥30s/轮**（含搜索耗时），边搜边抽——抓取在后台线程运行，不阻塞下轮搜索 |
| **抓取** | urllib（L1）→ scrapling get（L2）→ scrapling fetch（L3）三层降级 |
| **容错** | 任一引擎失败不影响另一路；双引擎都失败该轮为 0 结果，不阻塞整体流程 |
| **输出** | `web_search_data.json`（stock_news + industry_news，schema 不变） |

#### 子 Agent 自搜（v0.9 新增）

Step 0 采集是"初始投喂"，不是"全部信息"。子 Agent 发现信息缺口时，可**自主调用 ddgs_safe.py 补充搜索**：

```bash
python3 /home/admin/agent-skills/a-share-analyst-team/scripts/ddgs_safe.py -q "搜索词" -m 6 --json
```

> ddgs_safe.py v3.0 内部使用 Firecrawl + Baidu 双引擎并行，≥20s 文件锁限频。子 Agent 在 `delegate_task` context 内通过 `terminal` 调用。

#### 内容边界（关键）

**核心原则：只抓 API 管线采集不到的信息。** 行情、财务、估值已有专门接口，网络搜索做增量补充。

| ✅ 搜索覆盖（API 抓不到） | ❌ 不搜索（API 已有） |
|--------------------------|----------------------|
| 业务动态/产品/客户/竞争壁垒 | 股价/涨跌幅/成交量 |
| 技术进展/研发/专利/工艺突破 | PE/PB/估值分位 |
| 产能扩张/新项目/合作公告/合同 | 财务三表数据 |
| 行业趋势/政策法规/竞争格局变化 | 技术指标（MACD/KDJ/均线） |
| 网络舆情/媒体覆盖/争议事件 | 资金流向/北向资金 |
| 管理层变动/股权变更/重大事项 | 实时行情 |

> Agent 引用网络搜索结果时标注「网络公开信息」，与 API 数据区分层级。

#### 消费者

`web_search_data.json` → B1, B2, F1, F2, F, S

#### 使用方式

主 Agent 在 Step 0 S1 阶段执行：
```bash
python3 /home/admin/agent-skills/a-share-analyst-team/scripts/collect_web_search.py \
  --symbol {symbol} --name {name} --industry {industry} \
  --output {TASK_BASE}/data/web_search_data.json
```

### agent-m-brief.md

Agent M（材料归集师）在 v0.4 已下线——每份文档独立处理，无需合并。`agent-m-brief.md` 保留归档，不再调用。

### 材料使用纪律（全 Agent 适用）

**硬约束 13：时效性必标**

| 材料日期 | 标注 | 使用态度 |
|---------|------|---------|
| < 1 月 | 近期 | 正常参考 |
| 1-3 月 | 标注"已过 X 天" | 可用，但预测可能已失效 |
| 3-6 月 | ⚠️ 标注"较陈旧" | 仅定性逻辑可用，数字大概率已过时 |
| > 6 月 | ❌ 标注"严重过时" | 仅历史背景参考，不作为当前论据 |
| 无日期 | 默认标注 | 「用户提供材料，日期不详，时效性无法判断」 |

**硬约束 14：审慎不盲从**

- 材料数字是外部输入，不是系统验证数据。和 Step 0 API 数据冲突时，**Step 0 优先**
- 研报评级带券商名（「招商证券给买入」≠「市场共识买入」）
- 不把单家预测当一致预期
- 不因材料已有现成论据就跳过数据验证——材料是**补充**，不是**替代**

## ⛔ 数据纪律（系统级硬约束）

```
                    Step 0: 主 Agent 编排 9 子 Agent 采集
                    产出 9 个数据文件（含 F#10/F#11） → /tmp/{symbol}_{date}/data/
                              │
          ┌───────────────────┼───────────────────┐
          ↓                   ↓                   ↓
     Agent A context     Agent B context     Agent C context
     (F#1 only)           (F#3+F#4+F#6)          (F#2 only)
          │                   │                   │
          ⛔                    ⛔                   ⛔
     禁止自行拉数          禁止自行拉数         禁止自行拉数
```

1. **Step 0 产出的 9 个数据文件是子 Agent 的强制数据基础**；用户提供的材料文件（如有）为补充参考
2. 每个子 Agent 必须同时读取数据文件（见 `data-pipeline.md` 映射）和材料文件（如有，见 Phase 0d），不得选择性忽略
3. 子 Agent 不可调用任何数据获取函数（中间层/akshare/web_*）
4. 脚本从数据文件读输入，不自行拉数
5. 数据不足 → 标注「数据不足：缺少XXX」，不编造、不绕过、不降级
6. 主 Agent Step 0 是系统中唯一编排数据采集的实体
7. ⛔ **规模排名用全量分母**：总市值排名/营收排名/净利润排名必须使用行业全量企业数（含 ST），不得因估值分析剔除 ST 而缩小分母。如"全行业 80 家排名第 36"，不是"78 家排名第 36"

8. ⛔ **多源交叉验证置信跃升（v0.8.6 新增）**：web_search 单条信息不可作为独立论据，但多条独立来源朝同一方向收敛时，置信度来自**信号密度**而非来源权威性。B1 的「前瞻面聚合」（web_search + S + forecast 三源交叉验证）按密度定级——🔴强信号群（5+条含官方来源）权重等同 API 软数据，🔶多源交叉验证（3-4条）权重 = API 软数据 × 0.7。B3/F 裁决时不得以「非 API 数据」为由系统性压低交叉验证信号群的权重。

## 架构概览

```
Phase 0 (可选)       →  full_parse.py 解析 → table_extract.py 提取
                        → Agent R 审阅 → 精准分发
                        仅当用户提供文档附件时触发
                              ↓
数据层 (Step 0)     →  9 子 Agent 分三阶段采集 → 9 个数据文件
                        详见 references/data-pipeline.md (DAG)
                         ⏱ ~30s, 纯机械, 零推理
                              ↓
计算层 (子Agent调用)  →  16 个 Python 脚本: ta / scorer / signal / validator /
                        multi_tf / risk_quant / st_risk / earnings_surprise /
                        rotation / theme_detector / screener / st_penalties /
                        volume_classifier / volume_price / concentration
                         ⏱ 1-5s/脚本, 确定性计算, 零 LLM
                         ⛔ 每次任务必须在 {TASK_BASE}/ 下现场执行，禁止读预存输出
                              ↓
推理层 (16 Agent)    →  辩论架构: 正反辩论 + 独立裁判 + ST 风控 + 首席裁决 + 独立撰稿
                         ⏱ 900s/Agent 超时, 最大并行 3
```

## Agent 团队（含 Phase 0）

| 阶段 | Agent | 角色 | 输入数据 | 状态 |
|------|-------|------|---------|:--:|
| P0a | — | 文档解析（full_parse.py） | PDF → MD | ✅ |
| P0b | — | 表格提取（table_extract.py） | MD → JSON | ✅ |
| P0c | **R** | 文档审阅师 | 全量 MD | 🆕 v0.4 |
| P0d | — | 精准分发（主 Agent） | routing.json | 🆕 v0.4 |
| P1 | **A1** | 多头市场策略师 | market_data.json（指数/宽度/资金流/情绪/估值） | ✅ |
| P1 | **A2** | 空头市场策略师 | 与 A1 相同 | ✅ |
| P1b | **A3** | 市场裁判 | A1 + A2 报告 | ✅ |
| P1 | **B1** | 多头分析师 | valuation + forecast + profile + scale + 材料 + web_search | ✅ |
| P1 | **B2** | 空头分析师 | 与 B1 相同 | ✅ |
| P1b | **B3** | 基本裁判 | B1 + B2 报告 | ✅ |
| P1b | **C1** | 趋势派技术 | K线 + 实时行情 + 材料（仅含技术分析时） | ✅ |
| P1b | **C2** | 反转派技术 | 与 C1 相同 | ✅ |
| P1c | **C3** | 技术裁判 | C1 + C2 报告 | ✅ |
| P1c | **S** | 板块分析师 | industry_spot + industry_flow + 行业指数K线 + industry_valuation + web_search | 🆕 v0.8 |
| P1c | **D** | 资金博弈师 | flow + 材料 | ✅ |
| P2 | **P1** | 板块多头策略师 | S报告 + B3裁决 + C3裁决 + D报告 | ⏸️ TBD |
| P2 | **P2** | 板块空头策略师 | 与 P1 相同 | ⏸️ TBD |
| P2b | **P3** | 板块裁决官 | P1 + P2 报告 | ⏸️ TBD |
| P3 | **F1** | 错误论者 | A3/B3/C3/S/D 摘要 + web_search_data（主 Agent 提取） | ✅ |
| P3 | **F2** | 有效论者 | 与 F1 相同 | ✅ |
| P4 | **F** | 首席裁决官 | F1/F2 thesis + A3/B3/C3/S/D 摘要 + web_search_data（主 Agent 提取） | 🆕 v0.8 |
| P5 | **E1** | 左侧交易师 | F裁决 + C2 + B3 + S + D + A3 + K线 + 材料 | 🆕 v0.8 |
| P5 | **E2** | 右侧交易师 | F裁决 + C1 + B3 + S + D + A3 + K线 + 材料 | 🆕 v0.8 |
| P5b | **E3** | 交易裁决官 | E1 + E2 报告 + F裁决 | 🆕 v0.7 |
| P6 | **I** | 合规质控师 | 全部报告 + 源数据文件 + scripts_output/（含存在性校验）+ 材料（如有，按路由） | ✅ |
| P6 | **H** | 纠偏风控师 | 全部报告 + I报告 + risk_quant + st_risk + 材料（如有，按路由） | ✅ |
| P7 | **W** | 首席撰稿人 | 19 份全量报告 + F/E3 裁决 | 🆕 v0.8
> ⚠️ W 是执笔人，不是分析师。结论以 F/E3 裁决为准，W 只负责合稿、结构化、行文质量——不重新辩论、不推翻裁决、不自行下结论。

> ~~Agent M~~（材料归集师）v0.4 已下线——0a/0b 直接产出文件，不再需要合并步骤。
> Agent R 详见 `references/agent-r-brief.md`。

## 输出目录结构

```
{TASK_BASE}=/tmp/{symbol}_{date}/
├── docs/                          ← Phase 0a 解析产出
│   ├── doc1.md                    ← 全量 Markdown（full_parse.py）
│   └── ...
├── data/                          ← 数据文件
│   ├── market_data.json           ← Step 0 数据采集
│   ├── stock_kline.json
│   ├── stock_valuation.json
│   ├── stock_forecast.json
│   ├── stock_flow.json
│   ├── financial_data.json
│   ├── penalties.json
│   ├── doc1_tables.json            ← Phase 0b 提取（每文档一个）
│   ├── doc2_tables.json
│   ├── routing.json               ← Phase 0c 路由表
│   └── scripts_output/            ← 脚本 I/O
│       ├── ta_input.json / ta_output.json
│       ├── concentration_output.json
│       ├── risk_quant_output.json
│       └── ...
├── reports/                       ← Agent 报告
│   ├── A_市场策略.md
│   ├── B1_多头分析.md
│   └── ...
└── 最终报告落位:
    /home/admin/file-transfer/{symbol}_{名称}_投资论文_{date}_{HHMM}.md
```


## 使用方式
### 主 Agent 执行时序

```
用户请求 + 可选附件
        │
   ┌────┴────┐
   │ 有材料？ │
   └────┬────┘
   有   │   无
   ↓    │    ↓
Phase 0a ──→ Step 0
(full_parse)  (照旧)
   │         │
   ↓         │
Phase 0b     │
(table_extract)│
   │         │
   ↓         │
Phase 0c     │
(Agent R)    │
   │         │
   ↓         │
Phase 0d     │
(精准分发)    │
   │         │
   └────┬────┘
        ↓
   Step 1-12 (A1/A2→A3→B1/B2→B3→C1/C2→C3→S/D→[P1/P2/P3 ⏸️]→F1/F2→F→E1/E2→E3→I/H→W)
```

### Step 执行流程

详见 `references/data-pipeline.md`（DAG 图 + 源并发规则 + 消费者映射）。

主 Agent 职责：
1. 加载 `a-share-market` skill
2. 创建 `{TASK_BASE}=/tmp/{symbol}_{date}/` 目录结构
3. 按 DAG 分阶段派发 `delegate_task`（工具集 `["terminal","file"]`）
4. S1（数据采集第一波）：D1(market) ∥ D2(kline) ∥ D7(penalties) ∥ D8(factor_quality) ∥ D9(web_search) —— 无 em/bs 冲突，5 子 Agent 并行
5. S2（第二波，EM 独占）：D3(valuation) → D4(forecast) —— 串行，EM 跨子 Agent 需排队
6. S3（第三波，BS 独占）：D5(flow) → D6(financial) —— 串行，BS 严禁并发
7. Step 1: A1 ∥ A2 → Step 2: A3 ∥ B1 ∥ B2 → Step 3: B3 ∥ C1 ∥ C2 → Step 4: C3 ∥ S ∥ D → Step 7: F1 ∥ F2 → Step 8: F（纯裁决）→ Step 9: E1 ∥ E2 → Step 10: E3（交易裁决）→ Step 11: I → H → Step 12: W（撰稿，MiroFish 三阶段）
  [Step 5-6: P1/P2/P3 板块辩论组 ⏸️ TBD——S+基本面+技术+资金数据链已闭环，板块辩论后续补充]
7.1. ⛔ **裁决质量约束（v0.8）**：A3/B3/C3 各裁决官必须在报告中包含：
   - 裁决结论（多/空/中性，附确信度）
   - 关键判断依据（至少 3 条定量+定性理由，引用具体数据）
   - 双方论点分歧点及裁决理由
   F1/F2 只收裁决报告，不收辩论原稿——裁决不写透则下游全盲。
7.2. ⛔ **交易辩论约束（v0.8）**：E1/E2 无论左侧还是右侧立场，报告必须包含：
   - 建仓触发条件（具体价格位/量能/时间窗口，不写模糊描述）
   - 止损位和止盈规划（基于 F 定价区间 + 技术支撑/压力）
   - 当前条件是否满足——未满足时明确标注"条件待触发"，不写伪建仓计划
8. 验证全部文件就绪 → 最终报告写入 `/home/admin/file-transfer/`
9. ⛔ 派发 Agent I 时必须在 context 中包含 `{TASK_BASE}/data/` 和 `{TASK_BASE}/data/scripts_output/` 的完整路径
10. ⛔ Step 0 子 Agent 必须调用 `scripts/collect_*.py` 固化脚本，禁止现场写临时脚本。用法见 `data-pipeline.md`
11. ⛔ **因子质量（v0.5 新增，v0.8.2 机械化——改脚本产出）**：Step 0 中 `prepare_factor_quality.py` 已产出 `{TASK_BASE}/data/factor_quality.json`。C1/C2/C3/I/H 的 brief 中指定了此文件为输入，Agent 自行读取。主 Agent 无需手工注入。

   > ⛔ 已踩坑：2026-06-23 京泉华(002885)、2026-06-24 信维通信(300136) 两轮均遗漏因子注入。v0.8.2 改为脚本机械化产出，消除主 Agent 手工步骤。

7.5. ⛔ **步骤反馈规范**：主 Agent 每完成一个 Step 后，必须向用户发送进度简报。格式按 Step 类型分两档：

   **辩论 Step（含 vs 对）**：A1/A2、B1/B2、C1/C2、F1/F2、E1/E2。
   ```
   Step {N} 完成（{耗时}）。{Agent1} {≤20字结论} vs {Agent2} {≤20字结论}。派发 Step {N+1}：{下一批简写}。
   ```

   **单体/串行 Step**：A3、B3、C3、F、E3、I、H、W（D、S、P 如有也适用）。
   ```
   Step {N} 完成（{耗时}）。{Agent} {≤20字结论}。派发 Step {N+1}：{下一批简写}。
   ```

   **W 完成（终态）**：W 落盘后，额外输出全流程汇总表：
   ```
   {股票} 全流程完成

   | 指标 | 值 |
   |------|-----|
   | 总耗时 | ~{分钟}min |
   | Agent 报告 | {N} 份 |
   | 终稿 | {KB}KB / {路径} |

   裁决链：B3 {结论} → C3 {结论} → F {结论} → E3 {结论}
   ```

   通用规则：
   - 耗时：`total_duration_seconds` 取整为分钟（如 197.61s → 3.3min）
   - 一句话结论：≤20 字，只抓最核心判断
   - 下一批简写：用 ∥ 分隔并行 Agent（如 A3∥B1∥B2），→ 分隔串行（如 I→H）
   - 禁止跳步：每完成一个 Step 必须报，不允许合并多步

7.6. ⛔ **Step 6 派发 F Agent（首席裁决官 —— v0.6 重构，v0.7 前移至 Step 6）**：F 在 E1/E2 之前裁决定价有效性。派发前主 Agent 必须从 Step 1-4 的报告中提取摘要块，构造精简 context（~3000 字）：

   **a. 提取摘要（主 Agent 用 execute_code）：**

   ```python
   # 从 B3/C3/P/D/A 报告中提取关键段落作为摘要（注意：F 在交易层之前，不含 E）
   b3_summary = extract_summary(f"{TASK_BASE}/reports/B3_基本裁决.md", target="裁决结论+关键分歧+评级")
   c3_summary = extract_summary(f"{TASK_BASE}/reports/C3_技术裁决.md", target="裁决结论+关键分歧")
   p_position = extract_summary(f"{TASK_BASE}/reports/P_同业分析.md", target="估值分位+可比锚点")
   d_flow = extract_summary(f"{TASK_BASE}/reports/D_资金博弈.md", target="主力方向+筹码集中度")
   a_market = extract_summary(f"{TASK_BASE}/reports/A3_市场裁决.md", target="市场方向+阶段+确信度")
   ```

   **b. 构造 F context：**
   ```
   F1 thesis（全文路径：{TASK_BASE}/reports/F1_错误论.md）
   F2 thesis（全文路径：{TASK_BASE}/reports/F2_有效论.md）
   web_search_data（路径：{TASK_BASE}/data/web_search_data.json）
   B3 裁决摘要：___
   C3 裁决摘要：___
   S 板块分析路径：{TASK_BASE}/reports/S_板块分析.md
   D 资金信号：___
   A3 市场裁决：___
   ```

   **c. F 产出** → `{TASK_BASE}/reports/F_首席裁决.md`（1000-1500 字）。详见 `references/agent-f-brief.md`。

   **d. 产出后校验**：主 Agent 用 `execute_code` 逐项检查阿克曼三问、退出标准、确信度矩阵、一句话结论是否存在。缺失章节发回 F 重写（最多 1 次）。

7.7. ⛔ **Step 10 派发 W Agent（首席撰稿人 —— v0.6 新增 · MiroFish 三阶段模式，v0.7 移至 Step 10）**：

   W 接收 20 份上游报告全文 + F_首席裁决.md + E3_交易裁决.md + 源数据文件。采用 plan → section → reflect 三阶段：

   **a. W1 规划阶段**：W 通读 15 份原稿 → 产出 `reports/report_plan.md`（章节规划 + 数据锚点表 + 跨节依赖图 + 争议标注）。主 Agent 快速扫读确认无结构性错误后进入 W2。

   **b. W2 撰稿阶段**：W 逐节写作。每条论据标注来源报告 + 段落位置，每个数值标注来源文件 + 字段路径。计划只决定结构，内容从原稿提取。产出 `reports/W_投资论文_初稿.md`（15000-18000 字）。

   **c. W3 反思阶段**：W 收到初稿 + 反思清单。抽查 5 个关键数值 vs 源数据文件，检查论据完整性、跨节一致性、结构完整性、裁决逻辑链闭环。修正后输出终稿。

   **d. 最终校验**：主 Agent 用 `execute_code` 读终稿，逐节 regex 匹配标题。缺失章节发回 W 重写（最多 1 次）。仍缺失则标注 `[主 Agent 注：以下章节缺失——___]` 后发出。

   详见 `references/agent-w-brief.md`。

> **v0.7 路线**：因子质量个股面交叉校验（读 `stocks/{code}.json`），形成指数×个股 2×2 置信矩阵。尤其中小盘桶指数面无高区分因子，个股特异性信号将成为主要决策依据。

## 硬约束（不可违反）

1. 子 Agent **不能调用 `delegate_task`**（不可递归派发）
2. 子 Agent **不能调用 `web_search`/`web_fetch`** 获取行情数据（价格/PE/PB/涨跌幅/资金流向/技术指标）
   - ✅ 例外：B1/B2/S/F1/F2 可通过 `ddgs_safe.py` + `scrapling` 搜索 API 无法覆盖的信息（业务进展/行业动态/机构调研等），详见各 brief 「自主搜索能力」段
3. 子 Agent **不能调用任何中间层函数或 akshare**（行情/财务数据必须来自 Step 0 产出文件）
4. 子 Agent **所有指标数值必须从脚本输出文件直接读取**，引用格式：`文件名 → 字段路径 = 值`（如 `ta_output.json → ma.MA20 = 306.52`）。⛔ 严禁凭记忆写数字，严禁用「约」「大概」等模糊词
5. ⛔ **脚本必须现场执行，禁止读缓存**：每次任务启动后，所有脚本（concentration/risk_quant/scorer/signal/validator/volume_classifier/volume_price/ta/multi_tf/st_risk/earnings_surprise/rotation/theme_detector/screener/st_penalties）必须在本次任务目录下重新执行，写入新输出文件。**禁止**读取任何非本次任务产出的 JSON 文件（上一个任务残留、其他股票结果、预置样例等）。任务隔离后天然杜绝跨任务缓存，同一任务目录内的旧文件靠时间戳比对判别
6. ⛔ **脚本输出即铁证，严禁篡改**：脚本输出的每个数值、判定、等级必须原样写入报告。不准改动任何数字，不准将「中度控盘」手动改成「高度控盘」，不准将 4.29% 改成 1.93%。脚本输出与 Agent 主观判断冲突时，报告中写入脚本数值作为事实基准，另起一段标注「Agent 判断与脚本输出差异：___」（不得以 Agent 判断替代脚本输出）
7. 主 Agent 在 Step 0 **必须加载 `a-share-market` skill**
8. 最终报告中**关键数据必须标注来源文件+字段路径**
9. 所有脚本**必须有对应 test_**
10. **数据不够 → 标注，不编造**
11. ST 风险结论**必须区分**：量化红线（预测项，含可信度）+ 事实证据（不参与预测可信度）
12. 辩论 Agent（B1/B2、C1/C2、F1/F2）的**推理过程**必须始终从己方立场出发寻找论据、建立逻辑链，不在思考阶段自限或内耗己方立场。输出的是「该立场捍卫者能拿出的最佳论证」——统一用立场归属句式（如「多头论证如下」），禁止「我认为应该…」。各辩论 Agent 全力输出己方立场，不预判对手论点。综合权衡是裁决层（B3/C3/F）的职责。
13. **材料时效性必标**：引用用户材料时必须标注来源+日期。超过 3 个月标注"较陈旧"，超过 6 个月标注"严重过时"仅做背景参考。无日期的标注「日期不详，时效性无法判断」。
14. **材料审慎不盲从**：材料数字是外部输入，非系统验证数据。与 Step 0 数据冲突时 Step 0 优先。研报评级带券商名，不把单家预测当一致预期。材料是补充，不能跳过数据验证。
15. **Phase 0 不阻断 Step 0**：文档解析失败标注原因后继续，不影响数据采集和后续分析。
16. ⛔ **多元思维模型方法论约束（v0.8.7 新增）**——从芒格 15 思维模型诊断中提炼的五条可泛化硬约束，嵌入 B1/B2/B3/F/E1/E2/E3/H 七个 Agent brief：
    (a) **贝叶斯更新**（B3）：最新季度数据偏离一致预期 ≥30% 时，必须执行先验→新证据→后验三段式概率更新，禁止将超预期当「已兑现事实」
    (b) **价格弹性验证**（B1/B2）：价格→利润敏感性判断必须引用历史弹性系数，禁止 1:1 假设
    (c) **产能兑现率折算**（B2）：规划产能数据必须三档敏感性（悲观70%/基准60%/乐观45%），禁止当确定性利空
    (d) **Lollapalooza 对等**（F）：多空双方须有多因素共振论述，一方有而另一方无 → 盲区标注 + 裁决确信用下调半档
    (e) **基本面估值止损**（E1/E2/E3）：止损体系必须含基本面估值锚（净资产/清算价值/重置成本），纯技术止损无法保护基本面崩塌
17. ⛔ **北向资金字段释义**：`market_data.json` → `northbound_flow` 中 `northMoney` 是**北向成交额**（买卖合计），不是净流入。净流入需自行计算：`(amountHongKongToSH + amountHongKongToSZ) - (amountSHToHongKong + amountSZToHongKong)`。禁止将成交额当作净流入使用。北向成交额仅反映市场活跃度，不能直接等同于外资多空方向。
18. ⛔ **禁用线性外推——全局适用**：严禁任何形式的简单乘法外推（Q1×4、单月×12、单日×250 等）。周期股/季节股/高波动的标的，线性外推是系统性错误。前向估算必须满足以下至少一项：(a) 三档情景（乐观/基准/悲观）并标注每档假设和概率 (b) 引用一致预期作为外部锚 (c) 历史可比周期作为参照。确需引用单一数值时必须加「仅为外推参考，不构成预测」。此约束适用于 B1/B2/E1/E2/F1/F2 及任何涉及未来估计的 Agent。
19. ⛔ **进度汇报强制（v0.8.8 新增）**——主 Agent 每完成一个 Step 后，必须立即发送进度简报。格式：`Step{N}完成（{耗时}）。{Agent} {≤20字结论}。派发Step{N+1}: {下一批简写}`。贯穿 Step 0 到 W 落盘，**一步不许跳**，跳步 = 违规。W 落盘后额外输出全流程汇总表（总耗时/报告数/终稿路径KB/裁决链）。
20. ⛔ **终稿文件名含时分（v0.8.8 新增）**——终稿路径从 `{symbol}_{名称}_投资论文_{date}.md` 升级为 `{symbol}_{名称}_投资论文_{date}_{HHMM}.md`。
21. ⛔ **搜索引擎速限规范（v0.9 更新）**——Step 0 `collect_web_search.py` 已内置 3 轮 × ≥30s 间隔（含搜索耗时）。子 Agent 调用 `ddgs_safe.py` 自搜时，脚本内置 ≥20s 文件锁限频，无需手动控制。Firecrawl keyless 有 IP 级速率限制，连续高频调用可能触发 429。
22. ⛔ **子 Agent 必须知道自搜工具（v0.9 新增）**——主 Agent 派发每个子 Agent 时，context 中必须包含：
   - 对应 brief 的完整路径（如 `/home/admin/agent-skills/a-share-analyst-team/references/agent-b1-brief.md`）
   - 自搜工具声明：`可用自搜工具: python3 /home/admin/agent-skills/a-share-analyst-team/scripts/ddgs_safe.py -q "搜索词" -m N --json（v3.0 Firecrawl+Baidu双引擎，≥20s限频）`
   - 指示：`读取你的 brief 了解完整的分析框架、脚本调用和自搜模板。`
   派发 context 中缺少以上三项任一 → 🔴 阻断，补齐后重派。

## 已知陷阱（v0.2 积累）

### 中间层中文列名
K 线函数返回中文列名：`日期/开盘/收盘/最高/最低/成交量`，分钟 K 用 `时间`。
所有 `_parse_kline()` 的 col_map 必须包含中→英映射。

### terminal() 50KB 上限
`terminal()` stdout 有 50KB 截断。6MB 的 data_package 不能用 `terminal("cat ...")` 读，用 `execute_code` 的 `open()`。

### Shell JSON 传参不可靠
`terminal(f"python script.py --input '{json}'")` 中单引号/换行会被 shell 解释。
用文件传参或 stdin：`cat file | python script.py`。

### 分钟 K 线数据量少
新浪源 60min K 仅 ~16 根，multi_tf 标注「数据不足」而非崩溃。

### 周线数据来源
中间层无周线 API，`multi_tf.py` 内部从日线 resample 生成（~52 周），不再标「数据缺失」。

### ST 风险依赖财务中间层
R1-R4 定量分析需 `get_financial_abstract()` + `get_financial_indicators()`。
如财务中间层未安装或返回空，st_risk.py 标注 `data_insufficient`，不编造。

### 脚本缓存污染
不同任务/不同股票的脚本输出文件同名冲突。已由任务隔离（`{TASK_BASE}` + 硬约束 #5 脚本现场执行）解决。

### 子 Agent 输出与脚本输出不一致
Agent 可能篡改脚本结果的数字或判定。已由硬约束 #6（脚本输出即铁证）约束。

### I 质控缺少源数据
Agent I 只能做报告间交叉比对，无法验证报告数字与源数据是否一致。已修复：I brief 要求接收数据文件路径并用 read_file 逐字段比对。

### 中证A500/中证全指多周期涨跌幅缺失
FT 源不覆盖这两个指数，TX 仅提供当日涨跌幅。已由中间层 `_compute_period_returns()` 用 TX K 线自算补齐。

### EM API 瞬断
`stock_dzjy_hygtj` 等 EM 函数偶发 KeyError/超时。已加首次失败后随机 3~4s 重试一次。

### 脚本输出文件引用虚构（v0.4.1 新发现）
Agent E 运行 risk_quant.py/scorer.py 等脚本后，可能在报告里引用不存在的文件名（如 `risk_quant.json`），因为 Agent 从 stdout 读到值后直接编了引用路径而并未实际落盘。已修复：E brief 新增「脚本输出必须落盘后再引用」约束（保存到 `scripts_output/<script>_output.json`），I brief 新增「文件存在性校验」逐文件核实。
> 踩坑：2026-06-22 世运电路 I-03。

### I Agent 重算风险指标排序陷阱（v0.4.1 新发现）
risk_input.json 中 K 线可能是**降序**排列（最新在前）。I Agent 独立重算 VaR/波动率/回撤时，如果不对 `sort_values('date')` 就直接 `pct_change()`，收益率序列是时间倒流的——分布完全不同，导致 VaR_99、年化波动率、回撤持续天数等指标与 risk_quant.py 输出不一致。⛔ I Agent 重算前必须先检查排序方向。
> 踩坑：2026-06-22 I-02 误判——I Agent 在降序 K 线上直接算收益率，得 VaR_99=-7.91%，实际 risk_quant.py 的 sort→pct_change→percentile 路径得 -7.69%。E Agent 正确、I Agent 错误。

### F Agent 裁决与撰稿分离（v0.6 重构）

v0.5.1 中 F Agent 同时担任首席综合官（裁决 + 撰稿），认知负荷过大导致漏章（2026-06-23 天赐材料报告缺失阿克曼三问）。v0.6 拆为 F（首席裁决官，纯裁决 1000-1500 字）+ W（首席撰稿人，MiroFish 三阶段模式 12000-15000 字）。F 输入从 15 份全量报告压缩至摘要级 ~3000 字，裁决质量显著提升；W 独立撰稿 + 结构化反思，漏章风险降至最低。

### C2 Agent 独立重算 MA 偏离 ta.py（v0.6.1 新发现）

2026-06-23 京泉华(002885)实测中，C2 从 K 线数据独立重算了均线，使用了约 20 天前反弹峰值的旧数据（MA10=46.27 vs ta.py 最新值 41.75，偏差 4.52 元）。C2 据此判定「现价低于 MA10，短线偏弱」——但实际 MA10=41.75，现价 45.85 远高于 MA10。⛔ 已在 C1/C2 brief 的脚本段加入强制约束：MA 及其他技术指标必须从 ta.py 输出文件直接读取最新值，禁止各自重算。

### 因子质量注入遗漏（v0.6.1 新发现）

2026-06-23 京泉华实测中，主 Agent 派发 C1/C2/D/E1/E2 时跳过了因子质量注入步骤。面板数据（中证A500/中证500/科技桶）和个股因子数据（stocks/002885.json）均已就绪，但 context 中未包含因子质量键值对。⛔ 已在 SKILL.md §11e 加入阻断校验——主 Agent 在 delegate_task 调用前必须逐项检查 C1/C2/D/E1/E2 的 context 是否包含因子质量注入标记。

### E-D 依赖错位（v0.6.2 新发现）

2026-06-24 信维通信(300136)实测中，E Agent 在 D Agent 未完成时先行启动（D ∥ E 并行），导致 E 缺乏资金博弈数据。**根因**：E 的输入包含 D 的资金报告，但 DAG 将其设为并行。⛔ 已修复：DAG 调整为 Step 2: C1 ∥ C2 ∥ D（D 只需 Step 0 数据，无 agent 依赖），Step 4: E 独立等待 A+B3+C3+P+D 全部就绪。

### C3/validator 时序错位（v0.6.2 新发现）

2026-06-24 信维通信实测中，C3 用 MACD 死叉作为核心空头论据（权重 20%），但 validator 显示该股死叉后 20 日胜率 82%（反向指标）。validator 由 E 在 Step 4 运行，C3 在 Step 3 裁决时看不到该数据。⛔ 已修复：validator 前移到 C1/C2（Step 2），C1 验证趋势信号历史胜率、C2 验证反转信号历史胜率。C3 收到的 C1/C2 报告天然包含 validator 标注。

### F/E 时序错位（v0.7.0 新发现）

2026-06-24 信维通信及此前三次实测中，F 裁决（定价有效性）在 E 交易建议之后运行——E 在不知道市场是否错误定价的情况下就给出了买卖建议。⛔ 已修复：F1/F2→F 前移至 Step 4-5（在所有上游报告之后、交易层之前），E 拆为 E1（左侧）/E2（右侧）/E3（裁决），E1/E2 以 F 裁决为共同前置输入。

### E 单一体角色无法覆盖对立交易策略（v0.7.0 新发现）

原 E Agent 同时承担趋势跟随和逆势抄底两种矛盾的交易逻辑，在单一报告里无法展开充分辩论。⛔ 已修复：E 拆为 E1（左侧交易师，用 C2 反转信号）+ E2（右侧交易师，用 C1 趋势信号）+ E3（交易裁决官，裁决定价环境下哪种策略更适配），与 B1/B2→B3、C1/C2→C3 形成对称的三段辩论架构。

### C2 忽略周线约束 + C1 背离检测漏检（v0.8.6 新发现）

2026-06-27 信维通信(300136)实测中，C2 完全未涉及周线分析——在周线 MA20 斜率 +8.77%、MACD 零轴上方向上行的强约束下，C2 仍将日线顶背离推向"强力看空"8.4/10。C3 裁定此为"最大结构性缺陷"。同时 C1 的 ta.py 自动检测"未发现顶背离"，但 DIF 从 10.29 断崖跌至 2.91（-71.7%）客观存在——C1 的方法论盲区导致漏检。⛔ 已修复：C2 brief 新增周线分析强制约束（若周线强趋势成立，日线反转信号必须降权）；C1 brief 强化 multi_tf_result.json 的周线数据引用；两 brief 均明确周线数据路径和降权规则。

### 多元思维模型五盲区（v0.8.7 新发现）

2026-06-27 天赐材料(002709)多元思维模型诊断发现系统级方法论缺陷...

### 预执行框架回退（v0.8.7 撤回）

v0.8.5 引入的辩论脚本预执行（§7.5）因主 Agent 集中执行时 `--input "$(cat 文件)"` 触发 shell 参数上限（128KB），导致 8/10 脚本失败——而子 Agent 各自用 stdin 或 `--file` 跑从未出过问题。⛔ 已撤回：删除 §7.5，脚本恢复为子 Agent 在 delegate_task 内自行执行（stdin 管道）。预执行节省的 1-5 秒脚本时间 vs 100-200 秒 Agent 推理时间——收益可忽略。

### Baidu CAPTCHA 风险（v0.9 新增）

SearXNG 直连百度 JSON API 时，高频请求会触发百度 CAPTCHA（suspended_time=3600s）。v0.9 已将 Step 0 缩至 3 轮 × ≥30s 间隔来降低触发概率。双引擎架构（Firecrawl 主力 + Baidu 补中文）确保即使百度被封，Firecrawl 仍可独立产出结果。子 Agent 自搜同样受益于此容错设计——ddgs_safe.py v3.0 双引擎并行，百度挂了 Firecrawl 顶上。
