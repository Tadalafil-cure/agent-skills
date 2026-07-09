# 点金投顾侧分析模式借鉴

> 源：https://github.com/LucioSui/DianJin-SKILLS (investment-advisor 7 skill 深度学习)
> 日期：2026-06-18

## 一、核心可借鉴模式

### 1. 盘子大小修正逻辑（stock-tech-analysis）
大盘股(流通市值>1000亿)：PE偏低正常，重MA60/MA120长期均线，忽略短线KDJ
中小盘(流通市值<200亿)：PE高可能是成长溢价，重换手率和量能异动，技术指标易钝化

→ a-share-analyst-team 启示：PE/PB 解读时自动带市值分层修正

### 2. 统计基准体系（comparable-company-analysis）
除均值/中位/极值外，增加分位数(Percentile)和行业排名定位
目标公司在同行中的百分位 → 直观展示相对位置

→ 中等优先级，待 `get_industry_valuation_comparison` 加 `pe_ttm_percentile`

### 3. 交叉验证找真热点（a-market-hotspot-discovery）
板块涨幅排名 ∩ 资金流入排名 ∩ 资讯利好 → 真热点
只有涨幅没资金没资讯 → 纯情绪炒作，标注风险

→ a-share-analyst-team 缺少此交叉验证步骤

### 4. 资金面四维框架（stock-fund-analysis）
主流资金流向 / 北向机构资金 / 量能换手率 / 筹码集中度
多维度交叉验证，单一维度信号不可靠

→ 中间层已有对应函数（龙虎榜/大宗/股东户数/质押），team skill 已集成

### 5. 标准化输出模板
所有 7 个 skill 都有固定的 Markdown 输出模板 + 风险提示 + 审计追踪
→ a-share-analyst-team 可借鉴统一输出规范

## 二、与中间层对应关系

| 点金 skill | 中间层函数 |
|-----------|----------|
| stock-quote-analysis | get_realtime_quote + get_daily_kline |
| stock-tech-analysis | 同上 + 市值分层 |
| stock-fund-analysis | get_individual_fund_flow + get_lhb_stat + get_dzjy_stat |
| stock-shareholder-analysis | get_top10_shareholders + get_pledge_info + get_shareholder_count |
| stock-multi-factor-filter | 无直接对应 |
| comparable-company-analysis | get_industry_valuation_comparison + get_scale_comparison |
| a-market-hotspot-discovery | get_board_spot + get_board_fund_flow + get_concept_spot |

## 三、实施优先级

| 优先级 | 内容 | 状态 |
|:--:|------|:--:|
| P0 | `get_industry_valuation_comparison` 加 `pe_ttm_percentile` | 待做 |
| P0 | team skill 加审计追踪 | 待做 |
| P1 | team skill 启用已有函数（龙虎榜/大宗/股东/质押） | ✅ 已集成 |
| P1 | 热点交叉验证逻辑 | 待做 |
| P2 | 盘子大小修正 + 行业属性自适应权重 | 待做 |
