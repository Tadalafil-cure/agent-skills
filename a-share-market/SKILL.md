---
name: a-share-market
description: A 股行情中间层入口 —— 所有个股/板块/行业/指数/行情查询的唯一个个股。skill 即路由表，加载即就绪，不查外部文档。IPO 和财务另有独立 skill。
---

# A 股行情中间层

**本 skill 就是 a_share_market_middleware 的入口。** 中间层花了大量精力逐函数建设，绕过即浪费。

## ⛔ 强制触发条件（机械约束，不可跳过）

**任何涉及 A 股数据查询/分析的任务，`a-share-market` skill 必须在第一步加载。** 不加载=流程错误，无论结果对错。

加载后，**唯一合法的数据接入路径**是中间层函数（`from a_share_market_middleware.... import ...`）。

### 降级工具（仅中间层无法满足时使用）

以下工具不是"禁止"，而是**降级路径**——必须先尝试中间层函数，确认无法覆盖后才用：

| 工具 | 降级使用条件 |
|------|-------------|
| `browser_navigate` + `browser_console` | 中间层函数全部尝试后仍缺数据（如 PAE API 某字段不返回），浏览器抓取作为最后手段 |
| 裸 `requests.get` / `curl` | 中间层未覆盖的接口（如新发现的 API），且已标注「中间层未覆盖」 |
| `akshare` 直接调用 | 中间层路由表中不存在对应函数时，降级调 akshare |

**核心规则：中间层优先，能走中间层就走中间层。中间层兜不住的才降级。** 跳过中间层直接用降级工具 = 流程错误。

### 正确路径（唯一）

```
用户问 A 股 → 加载 a-share-market skill → 从 skill 路由表找到对应函数 → 调用中间层函数 → 取回数据 → 分析
```

**中间层函数返回的 `data` 和 `meta` 是分析的唯一数据来源。** 不做二次抓取、不"补充验证"、不"对比数据源"。

### 环境配置（一次性）

中间层已通过 `pip install -e` 注册为可编辑包，`execute_code` 和 `terminal` 均可直接 `from a_share_market_middleware.... import ...`，**无需 `sys.path.insert`、无需 `cd` 到项目目录**。

> 📦 安装细节和 root-owned egg-info 陷阱 → `references/install.md`

| 环境 | Python | 位置 |
|------|--------|------|
| `execute_code` | hermes-agent venv (`~/.hermes/hermes-agent/venv/`) | ✅ 已安装 |
| `terminal` | miniconda3 | ✅ 已安装 |

```python
# ✅ 当前正确用法 — execute_code 中直接 import
from a_share_market_middleware.stock.realtime import get_realtime_quote
from a_share_market_middleware.stock.kline import get_daily_kline
# ... 按路由表调用即可
```

⚠️ 若以后新增 pip 依赖（如 `curl_cffi`），需同步安装到两个环境：
```bash
pip install <pkg>                                    # terminal/miniconda
~/.hermes/hermes-agent/venv/bin/pip install <pkg>    # execute_code/venv
```

## 铁律

1. **本 skill 加载后，禁止对 A 股行情数据直接调 akshare**。所有命中函数走中间层。
2. **未命中才降级 akshare**，并标注「中间层未覆盖」。
3. **响应解读：`meta` 优先于 `data`**。问「最新/今天」→ 取 `meta.latest_*`，不取 `data[0]`。
4. **中间层优先，降级兜底**。`browser`/裸 HTTP/`akshare` 是降级工具，仅中间层无法满足时使用。直接跳过中间层用降级工具 = 流程错误。

## 调用规则

1. **同源并发 ≤2**：同一数据源的函数同时最多调 2 个。（新浪/腾讯/同花顺等各自不超 2）
2. **异源可并发**：不同源之间无限制，可同时并发（如 1 个新浪 + 1 个腾讯 + 1 个同花顺）。
3. **B/S 源例外**：Baostock 源**禁止并发**，必须串行单条调用。
4. **间隔 1~2s 随机**：分次串行调用时，每次间插 `random.uniform(1, 2)` 秒 sleep。
5. **Legulegu 源禁止并发**：legulegu **必须串行单条调用**，间隔 1~2s。并发触发限流（HTTP 200 空返 body），串行正常。此规则覆盖 congestion/ebs/buffett/index-basic-pe/pb/northbound/high-low 全部 legulegu 端点。
6. **Legulegu token 规范**：`/api/stockdata/*` 端点必须在 query params 中注入 `token`（MD5 日期哈希）。中间层 `_fetch_legulegu_market` 和 `_fetch_index_basic` 已内置注入，调用方无需手动传。直接调裸 API 时务必带 token。

---

## 完整路由表

### stock/ — 个股层（symbol=6位纯数字）

```python
# 行情
from a_share_market_middleware.stock.realtime import get_realtime_quote, get_realtime_quote_batch
get_realtime_quote("600519")
# 降级链：tx → ths → ft (tx: qt.gtimg.cn 21/23字段,三市,实时性最优,缺总/流通股本)

# 批量行情 — 单次请求取全行业 PE/PB（get_scale_comparison → 同行代码列表 → 本函数）
get_realtime_quote_batch(["600519", "000858", "300394"])
# → 0.03s 返回全部，含 市盈率-TTM / 市净率 / 总市值 / 流通市值

from a_share_market_middleware.stock.kline import get_daily_kline, get_minute_kline
get_daily_kline("600519")                                         # 默认365日历日
get_daily_kline("600519", "20260101", "20260601")
# 降级链：SH/SZ: tx_http → sina-ak → bs → ft
#         BJ:    tx_http → ft (sina/bs 北交所不支持)                 # 指定范围
# 降级链：SH/SZ → tx_http → sina-ak → bs → ft
#         BJ   → tx_http → ft（sina/bs 北交所不支持，跳过）
get_minute_kline("600519")                         # 无参→5min+30min+60min三输出（同源串行）
get_minute_kline("600519", period="5", end_date="20260601")  # 单输出
# 降级链：sina_http → tx_http → bs (BaoStock, 180天+历史)

# FT 源 (market.ft.tech)：日K用，X-Client-Name:web，三市含北交所，仅前复权，无日期参数用limit=N

# 名称搜索 — 公司名/关键词 → 代码列表（个股层入口门禁）
from a_share_market_middleware.stock.search import search_stock
search_stock("凯盛")
# → A股三市过滤，港股自动剔除，可转债标记类型=可转债
# → data: [{代码, 简称, 市场, 类型}, ...]

from a_share_market_middleware.stock.hot_rank import get_hot_rank
get_hot_rank("600519")  # 沪深，北交所返空

from a_share_market_middleware.stock.news import get_stock_news
get_stock_news("600519")

# 基本面
from a_share_market_middleware.stock.profile import get_company_profile
get_company_profile("600519")  # 主营/产品/经营范围

from a_share_market_middleware.stock.disclosure import get_cninfo_disclosure
get_cninfo_disclosure("600519", start_date="20250101", end_date="20260601")

from a_share_market_middleware.stock.penalty import get_regulatory_penalties
get_regulatory_penalties("600519", stock_name="贵州茅台")
# ⚠️ 北交所 920 股票必传 listing_date，否则新三板时期记录混入
get_regulatory_penalties("920123", stock_name="芭薇", listing_date="2023-01-01")

from a_share_market_middleware.stock.listing_date import get_listing_date
get_listing_date("920765")  # → {"listing_date": "2021-07-05", ...}
# 调用方固定流程：get_listing_date → 拿 listing_date → 传入 get_regulatory_penalties

from a_share_market_middleware.stock.research import (
    get_research_reports,
    get_profit_forecast_eps,
    get_profit_forecast_net,
    get_profit_forecast_detail,
    get_profit_forecast_metrics,
)
get_research_reports("600519")
get_profit_forecast_eps("600519")
get_profit_forecast_net("600519")
get_profit_forecast_detail("600519")
get_profit_forecast_metrics("600519")

# 股东
from a_share_market_middleware.stock.holder import (
    get_major_shareholders,
    get_top10_shareholders,
    get_shareholder_changes,
    get_shareholder_count,
    get_fund_holders,
)
get_major_shareholders("600519")
get_top10_shareholders("600519")
get_shareholder_changes("600519")
get_shareholder_count("600519")
get_fund_holders("600519")

# 资金
from a_share_market_middleware.stock.flow import get_individual_fund_flow
get_individual_fund_flow("300136")  # PAE 主力资金

# 龙虎榜
from a_share_market_middleware.stock.lhb import get_lhb_stat
get_lhb_stat("600519")             # 默认近一月，桥接 ext/lhb.py 全量扫描 → 按代码筛选
get_lhb_stat("002421", "近三月")   # 可选周期：近一月/近三月/近六月/近一年

# 大宗交易
from a_share_market_middleware.stock.dzjy import get_dzjy_stat
get_dzjy_stat("600519")            # 默认近半年（大宗交易频率低）
get_dzjy_stat("600519", "近一月")  # 可选周期

# 股票质押
from a_share_market_middleware.stock.gpzy import get_pledge_info
get_pledge_info("600519")          # 默认最近交易日，个股质押比例

# 融资融券
from a_share_market_middleware.stock.margin import get_margin_detail
get_margin_detail("600519", "2026-06-05")  # 个股融资融券明细（按代码+日期直查）

# 同业对比
from a_share_market_middleware.stock.comparison import (
    get_scale_comparison,               # 行业规模对比（市值/营收/净利润排名）
    get_industry_valuation_comparison,   # 行业估值对比（全量+精选双档 PE/PB）
)
get_scale_comparison("600519")
get_industry_valuation_comparison("300394")

# 全行业估值快照 — 双档：全量同行 + 精选6家（均以 TX 为基数）
get_industry_valuation_comparison("300394")
# → meta.full:     全行业 {count, count_profitable, count_loss, pe_scope, pe_ttm_mean/median, pb_mean/median}
# → meta.selected: 精选6家 {codes, count, count_profitable, count_loss, pe_scope, pe_ttm_mean/median, pb_mean/median}
# → data: 全量企业列表（按 PE 升序），每行含 市盈率-TTM/市净率/总市值/流通市值
# ⚠️ TX vs akshare PB 差异根因（MRQ vs 实时）→ references/tx-vs-akshare-valuation.md

# 质押
from a_share_market_middleware.stock.gpzy import get_pledge_info
get_pledge_info("600519")          # 默认最近交易日，个股质押比例

### sector/ — 板块层（行业+概念严格分离）

### 行业 vs 概念：按意图选择

| 用户问法 | → 侧 | 函数 |
|----------|------|------|
| "白酒板块成分股"、"XX行业涨跌" | **行业侧** | `get_board_cons` / `get_board_spot("industry")` |
| "什么概念涨得好"、"靶材有哪些票" | **概念侧** | `get_concept_spot` / `get_concept_cons` |
| "茅台是什么板块" | **行业侧** | `symbol_to_board("600519")` |
| 个股属于哪些概念 | ❌ 未实现 | 自下而上需求，待独立做 |

**行业侧（申万链，board.py）：** 严分类，个股→板块一对一，6 个函数。
```python
from a_share_market_middleware.sector.board import (
    symbol_to_board, resolve_board, get_board_list, get_board_cons,
    get_board_spot, get_board_fund_flow,
)
# 三条工具链：chain="live"(PAE快速扫盘) / "full"(新浪深度PE/PB) / "compare"(EM财务排名)
# 默认 chain="live"
# 板块无K线：同花顺分类≠申万，不可桥接
```

**概念侧（PAE 单源，concept.py）：** 多对多，纯市场描述，4 个函数（list/spot/cons/resolve）。PAE rn=1000 拉全 ~800 个概念。使用模式：spot 扫排名 → 锁定主题 → cons 深挖成分股。
```python
from a_share_market_middleware.sector.concept import (
    get_concept_list, get_concept_spot, get_concept_cons,
    resolve_concept,
)
# PAE 概念 API：blocks 用 typeCode=GN, rn=1000；constituents 返回 Result.list[]
# 完整覆盖：光伏/半导体/芯片/AI/光刻/靶材/白酒/军工/华为等全部 A 股标准概念
```
# resolve_concept(name) — 概念名模糊匹配（exact → contains 两级）
# 概念允许模糊匹配（不像行业那样严格），如 "钨"→"钨概念"
```

### 统一模糊入口（`resolve_sector`）

当用户问的板块名不明确是行业还是概念时（如 "半导体"、"白酒"、"钨概念"、"靶材"），使用 `resolve_sector` 自动路由：

```python
from a_share_market_middleware.sector import resolve_sector

resolve_sector("白酒")       # → industry, "白酒Ⅱ", root命中
resolve_sector("钨概念")     # → concept, "钨概念", 概念后缀→概念侧
resolve_sector("半导体")     # → industry, "半导体", 行业精确优先
resolve_sector("靶材")       # → 都不命中（PAE无靶材概念），返回两侧兜底
resolve_sector("银行")       # → industry, ambiguous, candidates=[...]
```

路由优先级：**概念后缀 → 行业精确 → 行业root → 概念包含 → 行业包含 → 兜底**。行业优先于概念（行业名更规范）。

```python
from a_share_market_middleware.sector.board import (
    symbol_to_board,
    resolve_board,
    get_board_list,
    get_board_cons,
    get_board_spot,
    get_board_fund_flow,
)

# ① 个股→板块桥接（EM 定方向 → PAE 给全景）
symbol_to_board("600519")
# 内部：EM get_scale_comparison → board="白酒Ⅱ" → get_board_cons
# → {"board": "白酒Ⅱ", "peers": [成分股+实时行情], "peers_count": 19}

# ② 板块名 → 申万规范名（exact→root→contains 三级匹配）
resolve_board("白酒")   # → "白酒Ⅱ" (match_type=root)
resolve_board("化学")   # → candidates: [化学制品,化学制药,...] (ambiguous)
resolve_board("汽车零部件")  # → "汽车零部件" (match_type=exact)

# ③ 板块实时行情排名
get_board_spot("industry")
# PAE → 131行业涨跌排名，含涨跌家数/领涨股/领跌股/板块涨跌幅

# ④ 行业资金流
get_board_fund_flow("industry")
# PAE → 162行业(31一级+131二级) 主力净流入/流入/流出/总成交额(亿元)
get_board_fund_flow("concept")
# PAE → 200概念 主力净流入/流入/流出/总成交额(亿元)
# 板块代码与 get_board_spot 一致，可按代码 join 价格+资金面

# ⚠️ EM vs PAE 分类差异
# EM(get_scale_comparison) 用旧版申万：银行Ⅱ（全放一起）
# PAE(get_board_cons) 用新版申万：股份制银行Ⅱ/国有大型银行Ⅱ/城商行Ⅱ/农商行Ⅱ
# → symbol_to_board 自动聚合 4 子板块（42只），其他 125/131 板块精确匹配
# → 已知 2 只边界股：000958(PAE多元金融/EM电力)、601965(PAE汽车服务/EM专业服务)，不影响功能

# ⑥ 财务规模对比（EM 工具链，全量无行情）
from a_share_market_middleware.stock.comparison import get_scale_comparison
get_scale_comparison("600519")  # 白酒同行23只 — 总市值/营收/净利润排名+行业均值/中值
get_scale_comparison("601689")  # 汽车零部件275只 — EM全量，远超PAE的202只
```

**软引导架构**：`sector/__init__.py` 的 docstring 含完整决策树表格，agent import 时自动看到，无需硬编码路由函数。走错侧时 error message 会指路（如 `get_board_cons("靶材","industry")` → "概念板块请走 `get_concept_cons`"）。两侧 docstring 也互相 ⚠️ 引用。此模式适用于任何「两套分类体系并列、由语义决定走哪侧」的场景。

**板块层完成度：行业 6/6 + 概念 3/3**

| # | 能力 | 源 | 状态 |
|---|------|-----|:--:|
| 1 | 板块列表 | PAE | ✅ |
| 2 | 板块行情排名 | PAE | ✅ |
| 3 | 成分股(行情) | PAE chain="live" | ✅ ~200只 |
| 4 | 成分股(PE/PB) | 新浪 chain="full" | ✅ 全量 |
| 5 | 成分股(财务对比) | EM chain="compare" | ✅ 全量+排名 |
| 6 | 行业资金流 | PAE | ✅ 162条 |
| — | 板块K线 | — | ❌ 已删除（无申万源） |

### 概念源全景（2026-06-12 发现）

| 源 | 概念名册 | 成分股 | K线 | 资金流 |
|------|:--:|:--:|:--:|:--:|
| PAE | 200（残缺⚠️） | ✅ | ❌ | ✅ |
| THS | 373（完整✅） | ❌ | ✅ | ⚠️ |
| 新浪 | 700+214（完整✅） | ⚠️ API挂 | ❌ | ❌ |
| EM | ✅ | ✅ | ✅ | ❌（CF封） |
| Futu | 3（美股） | 3（美股） | ❌ | ❌ |

**⚠️ PAE 概念致命缺陷**：200个概念几乎全是资源品细分（钨/钴/镍/铜/铅锌…）+市场结构标签（转融券/沪股通/融资融券…），**缺半导体/芯片/AI/光刻机/光伏/新能源/医药/白酒/军工等所有核心交易概念**。

**已发现但未集成**：
- THS `stock_board_concept_index_ths` — 概念K线（日频OHLCV），373概念全覆盖
- 新浪 `getHQNodes` → 热门概念 700 条（chgn_前缀）+ 概念板块 214 条（gn_前缀）
- 新浪 `getHQNodeData?node=chgn_730606` — 概念成分股，当前API全节点返回 Invalid service name（待恢复）

**当前架构**：概念侧 PAE 单源，名册+资金流可用，成分股覆盖残缺。THS 名册+K线待集成，新浪成分股等待 API 恢复。

PAE kline 端点 (`/vapi/v1/kline`) 存在但返回 null，板块/个股均空数据。
同花顺有板块 K 线但分类体系与申万不兼容，不可桥接。
EM 板块行情被 Cloudflare 封。
结论：申万 K 线缺口当前无可用数据源，搁置。

**基础设施**：`sector/sw_classify.py` — 新浪申万 node code 映射（sina_sw 源依赖），板块层自包含不依赖 ext。

### overall/ — 市场指数层

#### 路由决策表

| 用户问法 | → 函数 | 关键参数 |
|----------|--------|---------|
| "今天大盘怎么样/指数多少点" | `get_index_quotes()` | 无参，10 指数 |
| "上证指数最近走势" | `get_index_kline("000001", ...)` | 代码=6位数字 |
| "沪深300 PE/估值/分位数" | `get_index_pe("沪深300")` | **指数名**（非代码） |
| "科创50 PB是多少" | `get_index_pb("科创50")` | **指数名** |
| "上证指数加权PE" | `get_index_weight("上证指数")` | 仅3指数：上证/深证/创业板 |
| "新高新低/市场宽度" | `get_market_breadth()` | 无参 |
| "大盘拥挤度" | ~~`get_market_congestion()`~~ ⛔ 废弃 | legulegu API 2026-04-03 后停更，不可信 |
| "股债利差/入场时机" | `get_ebs()` | 无参 |
| "巴菲特指数/总市值GDP比" | `get_buffett_index()` | 无参 |
| "涨跌停家数" | `get_market_activity()` | 无参 |
| "北向资金/外资流向" | `get_northbound_flow()` | 无参 |
| "融资融券余额" | `get_margin_summary("2026-06-05")` | date=YYYY-MM-DD |

#### 指数估值：三套 API，按指数选

| 指数 | PE函数 | PB函数 | 备注 |
|------|--------|--------|------|
| 上证指数 | `get_index_weight` | `get_index_weight` | weight-pe，含加权PE/PB+分位，慢(4.4s) |
| 深证成指 | `get_index_weight` | `get_index_weight` | 同上 |
| 创业板指 | `get_index_weight` | `get_index_weight` | 同上 |
| 沪深300 | `get_index_pe` | `get_index_pb` | index-basic-pe/pb，含等权/加权/中位+分位 |
| 中证500 | `get_index_pe` | `get_index_pb` | 同上 |
| 中证1000 | `get_index_pe` | `get_index_pb` | 同上 |
| 科创50 | `get_index_pe` | `get_index_pb` | 同上 |
| 北证50 | `get_index_pe` | ❌ 无PB | csindex 降级，仅近20日PE |
| 中证A500 | `get_index_pe` | ❌ 无PB | csindex 降级，仅近20日PE |
| 中证全指 | `get_index_pe` | ❌ 无PB | csindex 降级，仅近20日PE |

```python
# 指数行情
from a_share_market_middleware.overall.index_quotes import get_index_quotes
get_index_quotes()  # 10大指数实时快照，0.3s
# 智能合并：ft(8指数+多周期涨跌+振幅) + tx(补A500/全指) → sina(降级直调HTTP)

from a_share_market_middleware.overall.index_ import get_index_kline, get_all_index_kline
# 参数：start_date/end_date 均为 YYYYMMDD，均可省略。start_date 默认 3 年前，end_date 默认今天。
get_index_kline("000001")                              # 上证近3年（默认）
get_index_kline("000300", "20260101")                  # 沪深300 从2026-01-01至今
get_index_kline("000688", "20250101", "20260601")      # 科创50 指定范围
# 降级链：ft(自算MA,~1000条/4年) → sina(含MA,≤2年) → csindex(对齐+MA) → tx_http(2000条) → bs
get_all_index_kline()                                  # 10大核心指数近3年（默认）
get_all_index_kline("20260101", "20260612")            # 指定范围批量

# 指数估值 — ⚠️ 参数是指数名，不是代码！
from a_share_market_middleware.overall.valuation import (
    get_index_pe, get_index_pb, get_index_weight,
)
get_index_weight("上证指数")  # PE/PB+分位（weight-pe，仅上证/深证/创业板）
get_index_pe("沪深300")       # PE+分位 → meta.latest_weighted_pe, latest_weighted_pe_pct
get_index_pb("科创50")        # PB+分位 → meta.latest_weighted_pb, latest_weighted_pb_pct
get_index_pe("北证50")        # csindex 降级，仅20日PE

# 市场温度指标 — 均为无参函数，最新值在 meta 里
from a_share_market_middleware.overall.market import (
    get_market_breadth, get_ebs,
    get_buffett_index, get_market_activity, get_northbound_flow,
    get_margin_summary,
)
get_market_breadth()    # → meta.latest_date, meta.latest_high20/low20
get_ebs()               # → meta.latest_hs300, meta.latest_ebs, meta.latest_ebs_ma
get_buffett_index()     # → meta.latest_buffett, meta.pct_all, meta.pct_10y（自算分位）
get_market_activity()   # → meta.stat_date（涨跌停家数单日快照）
get_northbound_flow()   # 南北向资金日频（2025-02~今），单位亿元
get_margin_summary(\"2026-06-10\")  # 融资融券汇总（融资/融券余额+买入额）
# date 不传或用未来日期 → 自动降级取最新可用日期
# 源分布：breadth(无auth直调,公开) / northbound(无auth直调,公开) 
#         ebs+buffett+index-basic-pe/pb(CSRF+token,复用valuation session)
# ⚠️ legulegu 全端点禁止并发，必须串行间隔1~2s
#         activity(akshare HTML抓取) / margin(composite混合)
# ⛔ get_market_congestion 已废弃 — legulegu 拥挤度 API 2026-04-03 后停更，数据滞后不可信
```

### ext/ — 扩展层（全市场扫描）

```python
# 龙虎榜
from a_share_market_middleware.ext.lhb import (
    get_lhb_detail, get_lhb_stock_statistic,
)
get_lhb_detail("20260601", "20260609")
get_lhb_stock_statistic("近一月")

# 大宗交易
from a_share_market_middleware.ext.dzjy import get_dzjy_active
get_dzjy_active("近一月")

# 股票质押
from a_share_market_middleware.ext.gpzy import get_pledge_ratio
get_pledge_ratio()

# 分析师
from a_share_market_middleware.ext.analyst import (
    get_analyst_rank, get_analyst_detail,
)
get_analyst_rank(2026)
get_analyst_detail("分析师ID")

# 形态扫描
from a_share_market_middleware.ext.rank import (
    get_breakout_high, get_breakout_low,
    get_ma_breakout_up, get_ma_breakout_down,
    get_volume_expand, get_volume_shrink,
    get_volume_price_rise, get_volume_price_fall,
    get_streak_up, get_streak_down,
    get_insurance_stake,
)
get_breakout_high("20日新高")
get_volume_expand()
get_streak_up()

# 估值扫描
from a_share_market_middleware.ext.value import get_allstock_value_snapshot
get_allstock_value_snapshot()  # 全市场1747只 PE/PB/PEG

# 选股器
from a_share_market_middleware.ext.ft_screener import get_ft_screener
get_ft_screener(order_by="change_rate desc", page_size=20)
get_ft_screener(filter='board = "BJSE"', order_by="change_rate desc")
get_ft_screener(filter='board = "XSHG_STAR"', order_by="market_cap_total desc", page_size=50)

# 板块映射
from a_share_market_middleware.ext.sina_classify import get_allstock_sector_mapping
get_allstock_sector_mapping("申万行业")  # 全市场板块→股票映射
```

---

## 统计输出规范

**任何含过滤的统计数据，必须显式拆分明细，禁用模糊表达。**

| ❌ 模糊 | ✅ 明确 |
|--------|--------|
| `86只中61只有效` | `86只同行 = 61盈利 + 25亏损 + 0无数据` |
| `PE 均值 331.67` | `PE(仅覆盖盈利企业, 61/86): 均值=331.67 中位=111.68` |
| `大部分有 PE` | `61/86 家盈利 (70.9%)，25 家亏损不计入 PE 统计` |

**强制字段**：涉及 PE 统计时，必须同时输出 `pe_scope`（标注覆盖范围）和 `count_profitable`/`count_loss`/`count_no_pe` 三路拆解。

**get_industry_valuation_comparison 双档对比范式**：
```
通信设备 (300394)
  Full:  86只 = 61盈利 + 25亏损 + 0无数据  PE中位=111.68
  Select: 6只(全盈利)                       PE中位=128.75
```
两档均以 TX 实时行情为基数，精选子集从 akshare 提取代码后同源重算，保证可比性。

---

## 响应解读

所有函数返回：`{"success": True/False, "data": [...], "source": "tx", "meta": {...}}`

### ⚠️ meta 优先原则

历史序列函数（breadth/congestion/ebs/buffett等）在 `meta` 中携带最新快照：

```python
r = get_ebs()
# ✅ 取最新值
latest = r["meta"]["latest_ebs"]
date = r["meta"]["latest_date"]
# ❌ 不要取 data[0]
```

### 分析完整性清单（每次市场分析必须覆盖）

> 🚀 **一键扫描**：`python3 scripts/market_scan.py` 批量拉取以下 10 个函数并写入 `/tmp/market_snapshot.json`，省去手动分批。详见 `scripts/market_scan.py`。

每次 A 股分析必须覆盖以下维度，遗漏任何一项视为不完整。

**⚠️ 层级边界硬约束**：个股/板块/市场三层数据不可混为一谈。分析报告必须按层分段，不能把市场级数据当个股信号。

| 层级 | 函数 | 检查项 | 作用域 |
|------|------|--------|:--:|
| **市场** | `get_index_quotes()` | 10 指数涨跌 | 宏观背景 |
| 市场 | `get_market_breadth()` | 新高/新低比 | 宏观背景 |
| 市场 | `get_ebs()` | 股债利差 vs MA | 宏观背景 |
| 市场 | `get_buffett_index()` | 巴菲特指数+分位 | 宏观背景 |
| 市场 | `get_northbound_flow()` | 北向成交额（市场级总盘子） | 宏观背景 |
| 市场 | `get_margin_summary()` | 融资融券余额（两市合计） | 宏观背景 |
| **板块** | `get_board_spot("industry")` | 行业 Top/Bottom 5 | 行业对比 |
| 板块 | `get_board_fund_flow("industry")` | 行业资金流向（板块成分股合计） | 行业对比 |
| 板块 | `get_concept_spot()` | 概念 Top/Bottom 10 | 行业对比 |
| 板块 | `get_board_fund_flow("concept")` | 概念资金流向 | 行业对比 |
| **个股** | `get_realtime_quote()` | 实时行情+PE/PB | 目标个股 |
| 个股 | `get_daily_kline()` | 走势+均线 | 目标个股 |
| 个股 | `get_individual_fund_flow()` | 主力资金（仅此一个是个股级资金） | 目标个股 |
| 个股 | `get_industry_valuation_comparison()` | 全行业 PE/PB 双档统计（TX 基数） | 目标个股 |
| 个股 | `get_profit_forecast_eps()` | Forward EPS+机构数 | 目标个股 |

> 📋 **深度分析工作流**（市场→行业→个股三层扫描 + 分批调用模板）→ `references/deep-analysis-pattern.md`
> 📋 **点金投顾侧分析模式借鉴**（量化修正/统计基准/交叉验证/输出规范）→ `references/dianjin-patterns.md`

| meta 字段 | 含义 | 出现于 |
|-----------|------|--------|
| `latest_date` | 最新数据日期 | breadth, congestion, ebs, buffett, northbound, activity, margin |
| `latest_high20/low20` | 最新20日新高/新低数 | breadth |
| `latest_congestion` | ~~最新拥挤度~~ ⛔ 废弃 | congestion（API 停更，勿用） |
| `latest_ebs` | 最新股债利差 | ebs |
| `latest_buffett` | 最新巴菲特指数(%) | buffett |
| `latest_weighted_pe` | 最新加权PE | get_index_pe / get_index_weight |
| `latest_weighted_pe_pct_range` | PE分位时间范围 | get_index_pe (如 "全历史 (2005-04-08 ~ 2026-06-11)") |
| `latest_weighted_pb` | 最新加权PB | get_index_pb / get_index_weight |
| `latest_weighted_pb_pct_range` | PB分位时间范围 | get_index_pb |
| — | — | — |
| `pct_all` | 全历史分位组 | get_index_weight / get_buffett_index |
| `pct_10y` | 近10年分位组 | get_index_weight / get_buffett_index |
| — | — | — |
| `latest_hs300` | 最新沪深300指数 | get_ebs |
| `latest_ebs_ma` | 股债利差均线 | get_ebs |
| `latest_marketcap` | 最新总市值(亿元) | get_buffett_index |
| `latest_gdp` | 最新GDP(亿元) | get_buffett_index |
| `stat_date` | 统计日期 | activity |

**分位结构说明**：`get_index_weight` 和 `get_buffett_index` 返回的分位是嵌套 dict：
```python
meta["pct_all"] = {"pe_ttm": 0.692, "pb": 0.327, "range": "2004-01-02 ~ 2026-06-11"}
meta["pct_10y"] = {"pe_ttm": 0.971, "pb": 0.563, "range": "近10年 (截止 2026-06-11)"}
```
`get_index_pe`/`get_index_pb` 仅一套全历史分位，保持扁平 `latest_weighted_pe_pct` + `_range`。

---

## 更新记录

### v1.0.2 (2026-06-17)
- **`get_scale_comparison` 重写**：绕过 akshare 1.18.64 的 filter bug（SECUCODE 和 CORRE_SECUCODE 双锁导致只返回 1 行），改为直调 EM datacenter API（source: em-datacenter-scale，pageSize=500）
- **`symbol_to_board` 修复**：因上述修复，行业归属恢复正常（如 300394→通信设备、002850→电池、000657→小金属）
- **`stock_zh_scale_comparison_em` 入黑名单**：`core/_blacklist.py` 已拦截
- 新增已知限制：`get_valuation_comparison` 8 行硬限、`get_ft_screener` 无 PE/PB、`get_allstock_value_snapshot` 为聚合数据
- 新增 `references/full-pe-pb-pipeline.md`：全行业 PE/PB 两步法（scale→realtime）
- 新增 `references/field-reference-scale.md`：`get_scale_comparison` 和 `symbol_to_board` 字段速查
- 陷阱区新增 #14~#16（估值行数限制、FT 无估值、快照聚合）
- 修复 `stock/flow.py`：PAE 资金流向返回 `'--'` 占位符时 `_parse_pae_pct` / `_parse_pae_amount` 崩溃，新增显式占位符检测 → 返回 None
- 环境依赖：pandas、akshare、baostock 需在 venv 中安装
- middleware 安装：若源目录 egg-info 属 root，需 `sudo chown -R admin:admin` 后 `uv pip install -e`

## 致命陷阱

⚠️ **统一排序：所有 data 均降序排列（最新在前，data[0]=最新）。**

无需区分 K 线/市场/估值系列——全部统一。取最新数据直接用 `data[0]`，取最早用 `data[-1]`。

`meta.latest_*` 同样指向最新值，不受排序影响。

## 致命陷阱（原）

⚠️ **详细签名/陷阱/北交所支持矩阵** → `API_REFERENCE.md`（同仓库根目录）
致命陷阱：
2. `get_top10_shareholders(symbol)` — 不传 date 自动取最新季度，akshare 默认是 2021 年！
3. ext/rank 的 `symbol` 不是股票代码！是 "创月新高" 等类型名！
4. overall/valuation 的 `index` 是指数名不是代码！如 "沪深300"。
5. 估值函数分三套 API，不同指数用不同函数：上证/深证/创业板→`get_index_weight`，沪深300/500/1000/科创50→`get_index_pe`/`get_index_pb`，北证50/A500/全指→仅 `get_index_pe`(csindex降级)。
6. ⚠️ @degrade 包装陷阱：如果给 @degrade 函数加默认值包装层，内部函数名必须和 register_source 的 func_name 一致！否则源查找失败、所有源都不尝试、静默返回错误。（踩坑：包装层 `get_index_kline` → 内部 `_get_index_kline`，register_source 也必须用 `"_get_index_kline"`）
7. ⚠️ `execute_code` 全面测试超时陷阱：5 分钟上限不够跑全量（15 个函数 × ~3s/个 + sleep）。分批跑或用 `terminal` 跑单函数测试。详见 `references/install.md` 验证步骤。
8. ⚠️ PAE 源返回 `'--'` 占位符：`get_individual_fund_flow` 在部分股票上因 PAE 返回 `--` 导致 float 转换崩溃。已在 `flow.py` 的 `_parse_pae_pct` / `_parse_pae_amount` 中修复 → 返回 None。
9. ⚠️ **`get_valuation_comparison()` 返回 list，不是 dict**：`v['data']` 是 `[{市盈率-TTM: ...}, ...]`，必须 `v['data'][0]`。PB 字段是 `市净率-MRQ` 不是 `市净率`，PE-FY1 是 `市盈率-FY1`。
10. ⚠️ **`get_individual_fund_flow()` 返回 list**：`f['data']` 是 `[{当日主力净流入: ...}, ...]`，字段是 `当日主力净流入` 不是 `主力净流入`，单位是**元**（需 /1e8 转亿）。
11. ⚠️ **`get_profit_forecast_eps()` 返回 list**：`e['data']` 是 `[{EPS均值: ..., 预测机构数: ...}, ...]`，EPS 字段是 `EPS均值` 不是 `FY1_EPS`。
12. ⚠️ **`symbol_to_board()` 返回顶层字段，无 data 包装**：`r['board']` 不是 `r['data']['board']`。peers 在 `r['peers']`，count 在 `r['peers_count']`。
13. ⚠️ **批量前先验一只**：多只股票一起跑时，先跑 1 只确认数据结构，再跑其余。一只报错全部白费。
14. ⚠️ **`get_valuation_comparison()` 只有 ~8 行**：EM API 硬限，非 akshare bug。全行业 PE/PB 走 `get_scale_comparison` → `get_realtime_quote` 两步法，见 `references/full-pe-pb-pipeline.md`。
15. ⚠️ **`get_ft_screener` 不含 PE/PB**：screen 返回行情/市值/涨跌字段，无估值数据。按行业选股可用 `industry_sector` filter，但 PE/PB 需另行取。
16. ⚠️ **`get_allstock_value_snapshot` 是全市场聚合**：非按股输出，是市场日均值序列。不可用于个股 PE/PB 查询。
17. ⚠️ **PE 统计必须三路拆解**：输出 PE 均值/中位时，必须同时说明 `count_profitable`/`count_loss`/`count_no_pe`。禁用 "61/86 有效" 这种模糊表达。`get_industry_valuation_comparison` 的 meta 已含 `pe_scope` 标注 + 三路拆解字段，直接引用即可，不要自算自报。
18. ⚠️ **EM API 字段映射陷阱**：`get_scale_comparison` 直调 EM datacenter，返回的 `SECURITY_CODE` 永远是目标股自身，`CORRE_SECURITY_CODE` 才是同行代码。字段映射必须用 CORRE 系列，否则所有行显示同一只股票。已修复但任何新接 EM API 时都要检查这一点。
19. ⚠️ **比较模块设计模式**：个股层比较模块只对外暴露两个全量函数（`get_scale_comparison` + `get_industry_valuation_comparison`），akshare 的 ~8 行封装（`get_valuation_comparison`）退为内部工具。财务中间层（`a-share-finance-middleware`）的 `get_dupont_comparison`/`get_growth_comparison` 标注了 TODO 待同模式重构。新增比较函数时遵循此模式。

## 已知数据限制

| 限制 | 影响范围 | 说明 |
|------|----------|------|
| `get_index_quotes` 返回 dict | data 是 `{"000001": {...}, ...}` 不是 list | 取上证指数用 `data["000001"]`，不是 `data[0]` |
| 盈利预测可能为空 | `get_profit_forecast_*()` | 零机构覆盖的股票返回 `data: []`，这本身就是风险信号 |
| `get_margin_detail` 可能失败 | 个股融资融券明细 | 部分日期/代码组合返回 `success: false`，用 `get_margin_summary` 替代 |

## 已知数据限制

| 限制 | 影响范围 | 说明 |
|------|----------|------|
| `get_index_quotes` 返回 dict | data 是 `{"000001": {...}, ...}` 不是 list | 取上证指数用 `data["000001"]`，不是 `data[0]` |
| 盈利预测可能为空 | `get_profit_forecast_*()` | 零机构覆盖的股票返回 `data: []`，这本身就是风险信号 |
| `get_margin_detail` 可能失败 | 个股融资融券明细 | 部分日期/代码组合返回 `success: false`，用 `get_margin_summary` 替代 |
| `get_valuation_comparison` 仅 ~8 行 | 行业估值对比 | EM API 硬限，翻页无效。全量 PE/PB 走两步法 → `references/full-pe-pb-pipeline.md` |
| 北向资金 | `get_northbound_flow()` | ✅ legulegu 源正常，300条日频(2025-03~今)，字段: `northMoney`(北向成交额)/`amountHongKongToSH`(沪股通)/`amountHongKongToSZ`(深股通)，单位亿元。注意字段名不是 `net_flow_north`！ |
| `get_margin_detail` 可能失败 | 个股融资融券明细 | 部分日期/代码组合返回 `success: false`，用 `get_margin_summary` 替代 |
| PE 统计不含亏损企业 | `get_industry_valuation_comparison` | `pe_scope="仅覆盖盈利企业 (PE>0)"`，亏损/无数据分别在 `count_loss`/`count_no_pe`。输出时三路拆解，禁用 "N/M 有效"。|

## 字段速查

**⚠️ 所有返回值的字段名是中文。不要臆断英文 key。调用前查 `references/field-reference.md`。**

| 常见错误 | 正确 |
|----------|------|
| `x['changePct']` | `x['涨跌幅']` |
| `x['boardName']` | `x['板块名称']` |
| `x['mainNetFlow']` | `x['主力净流入']` |

完整字段表 → `references/field-reference.md`

## 字段解读提示

| 现象 | 含义 | 不要误判为 |
|------|------|-----------|
| `市盈率-TTM` 为负数 | 公司亏损（TTM净利润<0） | ❌ 不是数据错误 |
| `市盈率-FY1/FY2/FY3` 为 NaN | 无机构覆盖该股票的盈利预测 | ❌ 不是API返回不全 |
| `PEG` 为 NaN | 无盈利预测或PE为负，无法计算 | ❌ 不是计算bug |
| `盈利预测` 返回 `data: []` | 0家机构覆盖 | ❌ 不是函数坏了 |
| 换手率 | ✅ 全覆盖 | tx_http 主源 + akshare 历史补全（SH/SZ），北交所 FT 源不返回 |

## 不在此 skill 覆盖的

- **财务数据**（财报/杜邦/成长对比）→ 第二中间层，独立包
- **IPO** → `a-share-ipo-info` skill（辅导备案/申报/上会/发行详情，5 个 akshare 函数）
- **分红送配/业绩预告/互动易/ESG 等小众域** → 保留 akshare 直接调用，标注「中间层未覆盖」
