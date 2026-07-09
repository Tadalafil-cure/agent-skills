---
name: multi-mental-model
description: 芒格多元思维模型诊断 —— 用 15 个思维模型对任何投资论文/市场叙事做「尸检」式交叉验证。源自 sixpenny 方法论 + 天赐材料应用案例。适配 a-share-analyst-team 产出报告的第二层审查。
version: 1.0.0
tags: [analysis, munger, mental-model, diagnosis, a-share, quality-control]
trigger: 用户请求对某投资论文章/市场叙事做「多元思维模型诊断」「芒格框架审查」「尸检分析」「交叉验证」时加载。也可作为 a-share-analyst-team 流程的独立诊断层。
---

# 芒格多元思维模型诊断

> 来源：sixpenny（上头资本）《屏蔽那些噪音吧》2026.06.24
> 首例应用：天赐材料（002709）投资论文诊断（顾弥，2026.06.25）

## ⛔ 核心纪律

1. **事实与情绪分离**：先把事实和情绪分开。「顺」≠「真」
2. **支持与证伪都摆**：诚实呈现双方证据，让模型自己说话
3. **断点定位**：叙事链的断裂处比整体判断更值钱
4. **结论不超数据**：核心变量数据缺失时，确信度必须下调
5. **不辩护、不攻击，只解剖**：把叙事当尸检对象

## 十五模型速查

### 第一组：产业与盈利本质

| # | 模型 | 检验问题 | 详情 |
|:--:|------|---------|:--:|
| 1 | 供需模型 | 需求是零和还是动态增长？ | [→](chapters/model-01-supply-demand.md) |
| 2 | 价格弹性 | 用高弹性段推断整个市场？ | [→](chapters/model-02-price-elasticity.md) |
| 3 | 瓶颈理论 | 卡脖子环节在哪？叙事错置了吗？ | [→](chapters/model-03-bottleneck.md) |
| 4 | 幂律分布 | 收益集中在头部还是被拉平？ | [→](chapters/model-04-power-law.md) |
| 5 | 能力圈 | 论据来源在能力圈内吗？ | [→](chapters/model-05-circle-of-competence.md) |

### 第二组：机会与胜率

| # | 模型 | 检验问题 | 详情 |
|:--:|------|---------|:--:|
| 6 | 安全边际 | 回归杀估值还是杀产业？ | [→](chapters/model-06-margin-of-safety.md) |
| 7 | 赛马赔率 | 好故事≠好赔率，赌了几件事？ | [→](chapters/model-07-horse-racing-odds.md) |
| 8 | 冲浪模型 | 真浪头在哪？站对了没？ | [→](chapters/model-08-surfing.md) |
| 9 | 二阶思维 | 一阶→二阶→三阶？ | [→](chapters/model-09-second-order-thinking.md) |
| 10 | Lollapalooza | 多因素共振还是单因素？ | [→](chapters/model-10-lollapalooza.md) |

### 第三组：认知边界

| # | 模型 | 检验问题 | 详情 |
|:--:|------|---------|:--:|
| 11 | 激励模型 | 谁在喊、为什么喊？ | [→](chapters/model-11-incentives.md) |
| 12 | 均值回归 | 回归杀的是什么？ | [→](chapters/model-12-mean-reversion.md) |
| 13 | 路径依赖 | 护城河在产品还是生态？ | [→](chapters/model-13-path-dependence.md) |
| 14 | 贝叶斯更新 | 新证据调多少概率？ | [→](chapters/model-14-bayesian-updating.md) |
| 15 | 反向思考 | 什么真正能杀死逻辑？ | [→](chapters/model-15-inversion.md) |

## 诊断工作流

参见 [诊断工作流](chapters/diagnostic-workflow.md)。三步法：

1. **提取核心论断**：把被诊断对象浓缩为一句话因果链
2. **逐模型检验**：15 模型逐项过筛，每项给 ✅强 / ⚠️中 / ⚠️弱 评级
3. **综合裁决**：三档 —— 论文成立 / 部分成立需修正 / 论文被证伪

## 已知案例

| 股票 | 诊断日期 | 对象 | 裁决 | 详情 |
|------|---------|------|------|:--:|
| 天赐材料 002709 | 2026.06.25 | Agent W 投资论文 | 部分成立，需修正 | [→](chapters/case-tianci-002709.md) |

## 与 a-share-analyst-team 的关系

本 skill 是 **独立诊断层**，不替代也不依赖 a-share-analyst-team。典型用法：

```
a-share-analyst-team 产出报告
        ↓
multi-mental-model 诊断（本 skill）
        ↓
修正建议 → 发回 W 重写 / 下调确信度 / 标注盲区
```

诊断结论可直接落盘为 `{TASK_BASE}/reports/mental_model_diagnosis.md`。

## 加载指南

诊断完成后按需加载各模型章节文件。典型组合：
- 快速诊断：仅用 SKILL.md 速查表 + 工作流
- 深度诊断：加载全部 15 模型章节 + 案例
