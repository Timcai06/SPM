# 交付层分类字典与字段映射（基于《事件分类框架4.13》）

## 1. 目的

本文把桌面文档 `/Users/tim/Desktop/事件分类框架4.13.docx` 拆成可落库、可交付、可建模对接的口径说明，服务于当前 **非 `int_` 正式表层**。

本文解决三件事：

1. 冻结当前交付层的分类口径。
2. 说明 DOCX 分类框架如何映射到现有正式表字段。
3. 标出当前已实现、待补数、待扩展的缺口。

## 2. 适用范围

### 2.1 正式交付表（source of truth）

- `structured_events`
- `companies`
- `company_profiles`
- `event_company_links`
- `company_relations`
- `stock_daily_quotes`
- `market_environment_daily`
- `sentiment_propagation_daily`
- `event_research_samples`

### 2.2 内部表（不作为最终交付契约）

所有 `int_` 开头的表只作为内部加工、对齐、增强、训练支撑层使用。

## 3. 本次冻结采用的判定原则

1. **非 `int_` 表优先**：分类口径优先落在正式表字段，不先重构内部表。
2. **先兼容现状，再预留扩展**：
   - `v1 有效口径`：当前正式表已经承载、当前代码已经产出。
   - `v2 预留口径`：DOCX 已提出，但现有正式表仍未完整承载。
3. **字段不乱改名**：优先通过字典、说明文档、枚举冻结来统一语义。
4. **DOCX 中“突发类”不提升为一级主体**：统一归入 `shock_source_type`，不与 `event_subject_type` 并列。
5. **粗粒度字段继续保留**：如 `industry_type`、`impact_scope` 先保持 v1 粒度，细分行业/跨资产影响放到 v2 扩展。

## 4. 当前交付层 v1 有效分类字典

下表表示：**当前正式表已经有字段承载，且线上库已经出现过这些值**。

| 维度 | 正式字段 | v1 有效值 | 主要表 |
| --- | --- | --- | --- |
| 事件驱动主体（一级） | `event_subject_type` | `政策类 / 公司类 / 行业类 / 宏观类 / 地缘类` | `structured_events`, `event_research_samples` |
| 影响持续周期 | `duration_type` | `脉冲型 / 中期型 / 长尾型` | `structured_events`, `event_research_samples` |
| 可预测性 | `predictability_type` | `突发型 / 预披露型` | `structured_events`, `event_research_samples` |
| 事件极性 | `sentiment` | `利好 / 利空 / 中性` | `structured_events`, `event_research_samples` |
| 时间导向 | `time_orientation` | `future_oriented / current_confirmed / retrospective` | `structured_events`, `event_research_samples` |
| 事件阶段 | `event_stage` | `预期 / 确认 / 落地/执行 / 反馈` | `structured_events`, `event_research_samples` |
| 冲击源类型 | `shock_source_type` | `自然灾害 / 公共卫生 / 安全事故 / 地缘政治 / 政策制度 / 技术系统冲击 / 其他` | `structured_events`, `event_research_samples` |
| 区域范围 | `region_scope` | `domestic / regional / overseas / global` | `structured_events`, `event_research_samples` |
| 影响范围（粗粒度） | `impact_scope` | `个股链条 / 行业 / 全市场` | `structured_events`, `event_research_samples` |
| 影响层级数值化 | `impact_level_score` | `1~4`（当前实现） | `event_research_samples` |
| 事件可信度 | `source_credibility_score` | 数值分，当前建议按 `3/2/1` 对齐 DOCX | `structured_events`, `event_research_samples` |
| 强触发词得分 | `trigger_word_score` | 非负整数 | `structured_events`, `event_research_samples` |
| 明确性得分 | `explicitness_score` | 非负整数 | `structured_events`, `event_research_samples` |
| 不确定性得分 | `uncertainty_score` | 非负整数 | `structured_events`, `event_research_samples` |
| 新颖度 | `novelty_score` | `0~100` 数值分 | `structured_events`, `event_research_samples` |
| 金额尺度 | `amount_scale` | 当前为文本枚举位，默认 `none` | `structured_events`, `event_research_samples` |

## 5. 需要立即补齐字典、但不必先改主表的口径

下表字段已经存在于正式表，但当前**字典化不充分**，需要先冻结说明，再做补数。

| 维度 | 正式字段 | v1 建议冻结口径 | 状态 |
| --- | --- | --- | --- |
| 信息来源渠道 | `source_type` | `官方文件 / 监管/交易所 / 公司公告 / 主流财经媒体 / 其他来源` | 已有字段，需补字典 |
| 信息来源渠道（v2 预留） | `source_type` | `行业协会 / 社交媒体转发` | 预留扩展 |
| 权威等级 | `authority_level` | `central / ministry / exchange / listed_company / top_media / general_media` | 已有字段，需补字典 |
| 权威等级（v2 预留） | `authority_level` | `industry_association / social_media` | 预留扩展 |
| 事件驱动主体（二级） | `event_subject_subtype` | 见下文二级分类冻结表 | 已有字段，需补字典 |

### 5.1 二级主体分类冻结表（v1）

`event_subject_subtype` 建议按一级主体做冻结；当前库内已出现值与 DOCX 语义对齐后，先收敛为下表：

| 一级主体 | `event_subject_subtype` v1 建议值 |
| --- | --- |
| 政策类 | `产业政策 / 监管政策 / 财政税收 / 货币金融 / 补贴政策 / 行业规范 / 未细分` |
| 公司类 | `业绩公告 / 重大合同 / 产能投产 / 产品发布 / 高管变动 / 股权变动 / 诉讼仲裁 / 回购增持 / 未细分` |
| 行业类 | `供需价格 / 展会峰会 / 技术标准 / 进出口政策 / 行业整合 / 未细分` |
| 宏观类 | `宏观数据 / 未细分` |
| 地缘类 | `贸易摩擦 / 国际制裁 / 区域冲突 / 外交关系 / 国际公约 / 未细分` |
| 冲击补充 | `公共卫生 / 安全事故 / 自然灾害 / 技术系统冲击`（若当前分类器仍落到二级主体，先允许入字典） |

说明：

- DOCX 中的 `财政政策 + 税收政策`，当前库先并入 `财政税收`。
- DOCX 中的 `货币政策`，当前库先并入 `货币金融`。
- DOCX 中的“突发类”相关项，不作为一级主体；优先进入 `shock_source_type`，必要时在 `event_subject_subtype` 保留兼容值。

## 6. DOCX 分类框架到当前正式表的映射

| DOCX 模块 | 当前正式字段 | 当前正式表 | 映射方式 | 覆盖情况 |
| --- | --- | --- | --- | --- |
| 事件驱动主体（一级） | `event_subject_type` | `structured_events`, `event_research_samples` | 直接映射 | 已覆盖 |
| 事件驱动主体（二级） | `event_subject_subtype` | `structured_events`, `event_research_samples` | 直接映射，但需冻结枚举 | 部分覆盖 |
| 信息来源 | `source_type` | `structured_events`, `event_research_samples` | 直接映射 | 部分覆盖 |
| 权威等级 | `authority_level` | `structured_events`, `event_research_samples` | 直接映射 | 部分覆盖 |
| 信源可信度 | `source_credibility_score` | `structured_events`, `event_research_samples` | 数值映射，建议按 `3/2/1` | 已有字段，需统一打分口径 |
| 影响持续周期 | `duration_type` | `structured_events`, `event_research_samples` | 直接映射 | 已覆盖 |
| 可预测性 | `predictability_type` | `structured_events`, `event_research_samples` | 直接映射 | 已覆盖 |
| 事件极性 | `sentiment` | `structured_events`, `event_research_samples` | 直接映射 | 已覆盖 |
| 时间导向 | `time_orientation` | `structured_events`, `event_research_samples` | 直接映射 | 已覆盖 |
| 事件阶段 | `event_stage` | `structured_events`, `event_research_samples` | 直接映射 | 已覆盖 |
| 冲击源类型 | `shock_source_type` | `structured_events`, `event_research_samples` | 直接映射 | 已覆盖 |
| 强触发词 / 明确性 / 不确定性 / 新颖度 | `trigger_word_score / explicitness_score / uncertainty_score / novelty_score` | `structured_events`, `event_research_samples` | 数值特征映射 | 已覆盖 |
| 金额规模 / 金额相对规模 | `amount_scale` | `structured_events`, `event_research_samples` | 当前仅保留尺度位，未完整细化 | 部分覆盖 |
| 影响层级 | `impact_scope + impact_level_score` | `structured_events`, `event_research_samples` | 粗粒度文本 + 数值化 | 部分覆盖 |
| 涉及公司数量 | `affected_company_count` | `event_research_samples` | 训练样本层承载 | 已覆盖 |
| 涉及行业数量 | `affected_industry_count` | `event_research_samples` | 训练样本层承载 | 已覆盖 |
| 产业链覆盖环节数 | 暂无正式字段 | - | 需落到图谱/样本增强层 | 缺口 |
| 区域覆盖范围 | `region_scope` | `structured_events`, `event_research_samples` | 当前仅粗粒度文本 | 部分覆盖 |
| 市场覆盖范围 | 暂无正式字段 | - | 需在 v2 补充 | 缺口 |
| 舆情热度 | `mention_count / media_count / heat_score / heat_growth_rate / heat_duration_days` | `sentiment_propagation_daily` | 直接映射 | 已覆盖 |
| 舆情情绪分歧 | `disagreement_score / sentiment_std / source_stance_divergence` | `sentiment_propagation_daily` | 直接映射 | 已覆盖 |
| 机构预期分歧 | 暂无正式字段 | - | 需接研报/一致预期数据 | 缺口 |
| 交易行为分歧 | 暂无正式字段 | - | 需接更完整行情与盘口数据 | 缺口 |
| 公司图关系 | `event_company_links / company_relations` | 正式表 | 事件-公司边、公司-公司边 | 已有骨架 |
| 市场环境 | `market_environment_daily` | 正式表 | 指数/广度/热度环境表 | 已有骨架 |

## 7. v2 预留扩展（DOCX 已提出，但当前正式表不宜直接硬改）

以下内容应视为 **下一阶段扩展口径**，暂不直接破坏 v1 正式表契约：

| 维度 | DOCX 建议 | 当前处理方式 |
| --- | --- | --- |
| 影响持续周期 | `反复催化型` | 暂列 v2 预留，不立即改 `duration_type` |
| 可预测性 | `渐进演化型` | 暂列 v2 预留，不立即改 `predictability_type` |
| 行业属性 | `医药 / 金融 / 地产建材 / 周期资源 / 交通运输 / 农业食品 / 公用事业 / 传媒通信` 等 | 先保持 `industry_type` 粗粒度，后续通过行业映射表扩展 |
| 影响范围 | `跨行业 / 跨市场 / 跨资产` | 先保留 `impact_scope` 三档；后续增加辅助字段 |
| 地域范围 | 省市国家数量 | 先保留 `region_scope`；后续再加 count 类字段 |
| 市场覆盖范围 | A股/港股/美股/期货/债券 | 需要新增正式字段 |
| 机构预期分歧 | 一致预期标准差、离散系数 | 需要外部研报/一致预期数据源 |
| 交易行为分歧 | 盘口、大单、资金流、振幅博弈 | 需要更完整行情/资金流数据 |

## 8. 当前库状态对应的结论（2026-04-16 快照）

1. `structured_events` 已经承载了大部分事件分类主字段。
2. `event_research_samples` 已把多数事件分类字段带入训练样本层。
3. `sentiment_propagation_daily` 已能承接 DOCX 中“热度/分歧度”这部分口径。
4. `company_relations`、`event_company_links` 已形成图边骨架，但仍偏轻量。
5. 当前最需要先做的不是大改主表，而是：
   - **补齐分类字典**
   - **冻结二级分类口径**
   - **然后按冻结口径扩充正式表数据**

## 9. 推荐执行顺序

### P0：先做字典冻结

1. 扩充 `label_dictionary`，至少覆盖：
   - `event_subject_subtype`
   - `source_type`
   - `authority_level`
   - `sentiment`
   - `event_stage`
   - `time_orientation`
   - `shock_source_type`
   - `region_scope`
   - `impact_scope`
2. 用本文作为正式口径说明，不直接重命名主表字段。
3. 后续分类器、QA、样本构建统一按本文解释字段。

### P1：再做正式表补数

1. `company_profiles`：上市日期、地区、国企标签、员工、股本。
2. `stock_daily_quotes`：成交额、换手率、复权因子、涨跌停判定。
3. `market_environment_daily`：北向资金、多指数、行业指数、融资融券。
4. `company_relations`：供应链、持股、同实控人、同概念等关系边。

### P2：最后做 v2 扩展

1. 细行业枚举。
2. 跨市场/跨资产影响字段。
3. 地域/产业链覆盖数量字段。
4. 机构预期分歧与交易行为分歧字段。

## 10. 结论

对当前项目来说，最稳妥的推进顺序是：

> **先冻结正式分类字典与字段语义，再补正式表数据，不先大改非 `int_` 主表结构。**

