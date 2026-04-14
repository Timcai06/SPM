# 完整变量字典总表框架

## 1. 目标

这份变量字典用于统一后续建模输入口径，把当前系统拆成五层：

1. 事件层
2. 公司画像层
3. 公司关系层
4. 个股行情层
5. 市场环境层

最终通过事件-股票样本表汇总为可训练输入。

## 2. 表级分工

### 2.1 事件层

表名：`structured_events`

用途：
- 定义事件是什么
- 给出事件分类、阶段、强度、范围、来源与解释

### 2.2 公司画像层

表名：`company_profiles`

用途：
- 定义公司是什么
- 给出行业、区域、主营、治理、规模、财务、创新等慢变量

### 2.3 公司关系层

表名：`company_relations`

用途：
- 定义公司与公司之间如何连接
- 给 GNN 提供边

### 2.4 个股行情层

表名：`stock_daily_quotes`

用途：
- 提供原始日频 OHLCV 与交易状态
- 给衍生特征和标签计算提供底层数据

### 2.5 市场环境层

表名：`market_environment_daily`

用途：
- 描述事件发生时的市场背景
- 提供指数、广度、风格、资金与风险偏好变量

### 2.6 最终样本层

表名：`model_event_samples`

用途：
- 聚合事件、公司、关系、行情、市场环境与标签
- 直接交给建模同学

## 3. 变量字典

### 3.1 事件特征字典

来源表：`structured_events`

| 字段名 | 中文名 | 含义 | 说明 |
|---|---|---|---|
| `event_id` | 标准事件编号 | 同一类标准事件的业务编号 | 可重复映射到多篇原始文档 |
| `event_name` | 标准事件名 | 事件的统一命名 | 用于人工理解和报告展示 |
| `event_date` | 事件日期 | 事件发生或披露日期 | 训练和标签的时间锚点 |
| `event_subject_type` | 一级事件类型 | 政策类/公司类/行业类/宏观类/地缘类 | 事件主分类 |
| `event_subject_subtype` | 二级事件类型 | 如产业政策、监管政策、业绩公告、重大合同等 | 细化分类 |
| `industry_type` | 行业属性 | 科技/消费/军工/新能源/其他等 | 事件主要影响行业 |
| `duration_type` | 持续周期 | 脉冲型/中期型/长尾型 | 决定影响持续时间 |
| `predictability_type` | 可预测性 | 突发型/预披露型/渐进型 | 决定事件是否事前可见 |
| `sentiment` | 事件极性 | 利好/利空/中性 | 方向性标签 |
| `time_orientation` | 时间导向 | `future_oriented` / `current_confirmed` / `retrospective` | 事件叙事面向未来还是回顾 |
| `event_stage` | 事件阶段 | 预期/确认/落地执行/反馈 | 决定影响阶段 |
| `shock_source_type` | 冲击源类型 | 政策制度/地缘政治/安全事故/自然灾害等 | 解释冲击来源 |
| `impact_scope` | 影响范围 | 个股/行业/跨行业/市场整体/跨市场 | 影响层级 |
| `region_scope` | 地域范围 | 国内/区域/境外/全球 | 影响覆盖地域 |
| `source_type` | 来源类别 | 官方文件/监管交易所/公司公告/主流财经媒体/其他来源 | 文本来源分层 |
| `authority_level` | 来源层级 | `central` / `ministry` / `exchange` / `listed_company` / `top_media` / `general_media` | 来源权威性等级 |
| `source_credibility_score` | 来源可信度分 | 1-3 分 | 数值化来源可信度 |
| `trigger_word_score` | 触发词强度分 | 强触发词命中强度 | 如重大/首次/突破/超预期 |
| `explicitness_score` | 明确性分 | 文本是否包含明确金额、比例、对象、时间 | 越高越明确 |
| `uncertainty_score` | 不确定性分 | 拟/计划/预计/可能等词的强度 | 越高越不确定 |
| `novelty_score` | 新颖度分 | 与历史相似事件相比的新颖程度 | 第一版为规则分 |
| `amount_scale` | 规模量级 | none/small/medium/large/huge | 事件中涉及金额或规模量级 |
| `heat_score` | 热度分 | 媒体关注度和重复报道强度 | 文本热度近似值 |
| `intensity_score` | 冲击强度分 | 事件本身冲击强度 | 基于主体、关键词和冲击类型 |
| `event_code` | 事件编码 | 事件类型编码 | 用于规则化分析 |
| `event_summary` | 事件摘要 | 事件的短摘要 | 用于解释和人工检查 |
| `subject_entities` | 主体实体 | 涉及的主体实体列表 | JSON 数组 |
| `classification_evidence` | 分类证据 | 规则和 LLM 证据串 | 便于复核 |

### 3.2 公司画像特征字典

来源表：`company_profiles`

| 字段名 | 中文名 | 含义 | 说明 |
|---|---|---|---|
| `ts_code` | 股票代码 | 公司唯一代码 | 样本主键之一 |
| `company_name` | 公司简称 | 公司名称 | 展示字段 |
| `industry_l1` | 一级行业 | 申万一级行业 | 节点重要属性 |
| `industry_l2` | 二级行业 | 申万二级行业 | 更细粒度分类 |
| `region` | 注册地区 | 公司地域归属 | 区域政策事件有用 |
| `list_date` | 上市日期 | 上市时间 | 可衍生上市天数 |
| `state_owned_flag` | 是否国企 | 是否央国企/地方国企 | 治理与政策敏感度 |
| `company_type` | 公司性质 | 民营/国企/混改等 | 补充身份属性 |
| `business_scope` | 主营业务 | 主营业务描述 | 文本画像 |
| `core_products` | 核心产品 | 公司核心产品列表 | JSON 数组 |
| `concept_tags` | 概念标签 | 公司题材概念列表 | JSON 数组 |
| `employees` | 员工人数 | 公司规模侧面指标 | 慢变量 |
| `total_shares` | 总股本 | 股本规模 | 配合市值使用 |
| `float_shares` | 流通股本 | 流通盘规模 | 流动性解释变量 |

建议后续补充：
- `controller_type`
- `is_high_tech`
- `is_srdi`
- `revenue`
- `net_profit`
- `revenue_yoy`
- `net_profit_yoy`
- `roe`
- `debt_ratio`
- `rd_intensity`
- `patent_count`
- `inst_holding_ratio`

### 3.3 公司关系特征字典

来源表：`company_relations`

| 字段名 | 中文名 | 含义 | 说明 |
|---|---|---|---|
| `source_company_id` | 源公司ID | 边起点 | GNN 边起点 |
| `target_company_id` | 目标公司ID | 边终点 | GNN 边终点 |
| `relation_type` | 关系类型 | 上下游/同概念/同实控人/合作/竞争等 | 核心边类型 |
| `direction` | 关系方向 | 单向/双向 | 传导方向 |
| `relation_strength` | 关系强度 | 0-1 | 量化边权 |
| `evidence` | 证据 | 关系证据描述 | 便于人工校验 |

建议后续补充：
- `relation_source`
- `industry_chain_level`
- `effective_from`
- `effective_to`
- `is_verified`
- `same_controller_flag`
- `concept_overlap_count`
- `industry_overlap_count`

### 3.4 个股行情特征字典

来源表：`stock_daily_quotes`

| 字段名 | 中文名 | 含义 | 说明 |
|---|---|---|---|
| `ts_code` | 股票代码 | 股票唯一代码 | 行情主键之一 |
| `trade_date` | 交易日 | 日频时间 | 行情主键之一 |
| `open` | 开盘价 | 原始行情 | OHLCV |
| `high` | 最高价 | 原始行情 | OHLCV |
| `low` | 最低价 | 原始行情 | OHLCV |
| `close` | 收盘价 | 原始行情 | OHLCV |
| `pre_close` | 前收盘价 | 原始行情 | 收益计算基准 |
| `pct_chg` | 涨跌幅 | 原始行情 | 单日变化 |
| `volume` | 成交量 | 原始行情 | 活跃度 |
| `amount` | 成交额 | 原始行情 | 活跃度 |
| `turnover_rate` | 换手率 | 原始行情 | 交易强度 |
| `adj_factor` | 复权因子 | 复权支持 | 可选 |
| `is_suspended` | 是否停牌 | 交易状态 | 状态变量 |
| `is_st` | 是否ST | 风险状态 | 状态变量 |
| `is_limit_up` | 是否涨停 | 极端交易 | 状态变量 |
| `is_limit_down` | 是否跌停 | 极端交易 | 状态变量 |

建议后续从该表派生：
- `daily_return`
- `ret_3d`
- `ret_5d`
- `ret_10d`
- `ret_20d`
- `volatility_5d`
- `volatility_20d`
- `max_drawdown_20d`
- `industry_excess_return`
- `market_excess_return`

### 3.5 市场环境特征字典

来源表：`market_environment_daily`

| 字段名 | 中文名 | 含义 | 说明 |
|---|---|---|---|
| `trade_date` | 交易日 | 市场环境日期 | 主键 |
| `benchmark_code` | 基准代码 | 如 HS300 | 基准信息 |
| `benchmark_name` | 基准名称 | 基准展示名 | 基准信息 |
| `index_return_1d` | 基准单日收益 | 市场背景 | 基准收益 |
| `index_return_5d` | 基准五日收益 | 市场背景 | 趋势变量 |
| `index_volatility_20d` | 基准20日波动率 | 市场波动 | 风险环境 |
| `market_turnover` | 全市场成交额 | 市场活跃度 | 风险偏好 |
| `up_count` | 上涨家数 | 市场广度 | 情绪变量 |
| `down_count` | 下跌家数 | 市场广度 | 情绪变量 |
| `limit_up_count` | 涨停家数 | 极端情绪 | 情绪变量 |
| `limit_down_count` | 跌停家数 | 极端情绪 | 情绪变量 |
| `northbound_net_flow` | 北向资金净流入 | 资金面 | 风格和风险偏好 |
| `sector_hotness` | 板块热度 | JSON 板块热度 | 主题环境 |
| `cross_market_count` | 跨市场联动数 | 跨市场背景 | 可选 |
| `risk_on_off_score` | 风险偏好分 | 市场风险状态 | 汇总指标 |

### 3.6 最终样本特征字典

来源表：`model_event_samples`

| 字段名 | 中文名 | 含义 | 说明 |
|---|---|---|---|
| `sample_key` | 样本键 | `(event, company, date)` 唯一键 | 样本唯一标识 |
| `structured_event_id` | 结构化事件ID | 关联事件主表 | 外键 |
| `company_id` | 公司ID | 关联公司主表 | 外键 |
| `event_id` | 标准事件编号 | 事件业务编号 | 事件侧特征 |
| `event_date` | 事件日期 | 时间锚点 | 标签对齐 |
| `ts_code` | 股票代码 | 公司代码 | 样本主体 |
| `event_subject_type` | 一级事件类型 | 事件主分类 | 事件特征 |
| `event_subject_subtype` | 二级事件类型 | 更细分类 | 事件特征 |
| `source_type` | 来源类别 | 文本来源 | 事件特征 |
| `authority_level` | 来源层级 | 来源权威性 | 事件特征 |
| `source_credibility_score` | 来源可信度分 | 1-3 分 | 事件特征 |
| `duration_type` | 持续周期 | 影响周期 | 事件特征 |
| `predictability_type` | 可预测性 | 是否提前可见 | 事件特征 |
| `event_industry_type` | 事件行业属性 | 事件影响行业 | 事件特征 |
| `sentiment` | 事件极性 | 利好/利空/中性 | 事件特征 |
| `time_orientation` | 时间导向 | 面向未来或回顾 | 事件特征 |
| `event_stage` | 事件阶段 | 预期/确认/落地/反馈 | 事件特征 |
| `shock_source_type` | 冲击源类型 | 政策/地缘/事故等 | 事件特征 |
| `region_scope` | 地域范围 | 国内/全球等 | 事件特征 |
| `trigger_word_score` | 触发词强度分 | 强触发词命中强度 | 事件特征 |
| `explicitness_score` | 明确性分 | 信息清晰程度 | 事件特征 |
| `uncertainty_score` | 不确定性分 | 模糊程度 | 事件特征 |
| `novelty_score` | 新颖度分 | 新旧程度 | 事件特征 |
| `amount_scale` | 金额规模档位 | 规模量级 | 事件特征 |
| `event_code` | 事件编码 | 编码化事件类型 | 事件特征 |
| `heat_score` | 热度分 | 媒体关注度 | 事件特征 |
| `intensity_score` | 强度分 | 冲击强度 | 事件特征 |
| `impact_scope` | 影响范围 | 影响层级 | 事件特征 |
| `impact_level_score` | 影响层级分 | 数值化影响层级 | 事件特征 |
| `link_type` | 关联类型 | 事件-公司关系类型 | 关系特征 |
| `final_link_score` | 最终关联分 | 事件到公司的关联强度 | 关系特征 |
| `affected_company_count` | 受影响公司数 | 同事件命中的公司数 | 关系特征 |
| `affected_industry_count` | 受影响行业数 | 同事件命中的行业数 | 关系特征 |
| `relation_rank_in_event` | 公司排序 | 同事件候选中的排序 | 关系特征 |
| `industry_match_score` | 行业匹配分 | 事件行业与公司行业匹配程度 | 关系特征 |
| `concept_match_count` | 概念命中数 | 事件与公司题材交集 | 关系特征 |
| `event_age_days` | 事件到交易日间隔 | 事件与交易对齐距离 | 时间特征 |
| `event_trade_alignment_type` | 交易日对齐类型 | exact/prev/next | 时间特征 |
| `total_mv` | 总市值 | 公司规模 | 公司特征 |
| `circ_mv` | 流通市值 | 公司规模 | 公司特征 |
| `pe_ttm` | 市盈率 | 估值 | 公司特征 |
| `pb` | 市净率 | 估值 | 公司特征 |
| `turnover_rate` | 换手率 | 活跃度 | 公司特征 |
| `volume_ratio` | 量比 | 活跃度 | 公司特征 |
| `trailing_return_5d` | 近5日收益 | 动量 | 公司特征 |
| `trailing_return_20d` | 近20日收益 | 动量 | 公司特征 |
| `trailing_return_60d` | 近60日收益 | 动量 | 公司特征 |
| `volatility_5d` | 近5日波动率 | 风险 | 公司特征 |
| `volatility_20d` | 近20日波动率 | 风险 | 公司特征 |
| `volatility_60d` | 近60日波动率 | 风险 | 公司特征 |
| `up_days_20d` | 近20日上涨天数 | 趋势稳定度 | 公司特征 |
| `label_car_w1` | 1日 CAR 标签 | 事件研究标签 | 监督信号 |
| `label_car_w3` | 3日 CAR 标签 | 事件研究标签 | 监督信号 |
| `label_car_w5` | 5日 CAR 标签 | 事件研究标签 | 监督信号 |
| `label_up_w1` | 1日上涨标签 | 分类标签 | 监督信号 |
| `label_up_w3` | 3日上涨标签 | 分类标签 | 监督信号 |
| `label_up_w5` | 5日上涨标签 | 分类标签 | 监督信号 |

## 4. 推荐优先级

### 第一优先级

- `structured_events`
- `company_profiles`
- `company_relations`
- `stock_daily_quotes`
- `market_environment_daily`
- `model_event_samples`

### 第二优先级

- `sentiment_propagation_daily`
- 更细的公司治理与财务字段
- 更细的产业链依赖比例和合作强度

## 5. 当前系统与变量框架的对应关系

当前已基本具备：
- `raw_documents`
- `structured_events`
- `company_relations`
- `stock_daily_quotes`（原始行情表已建，数据仍需扩）
- `model_event_samples`

当前仍需重点补齐：
- `company_profiles`
- `market_environment_daily`
- `sentiment_propagation_daily`

## 6. 后续落地原则

1. 原始层与衍生层分开  
`stock_daily_quotes` 只放原始行情，`int_company_stats` 只放衍生特征。

2. 事件层与样本层分开  
`structured_events` 只定义事件，`model_event_samples` 只定义样本。

3. 交付层与内部层分开  
交付层用 8 张表，内部层继续保留 `int_*` 表做生产辅助。

4. 所有字段优先保证可解释  
先做规则稳定字段，再补高阶特征，不先追求过度复杂。
