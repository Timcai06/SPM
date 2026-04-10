# 任务1规则说明（答辩版，一页）

## 1. 规则版本与目标

- 规则版本：`task1_rules_v1`
- 目标：从原始文本中识别“具有金融影响意义的事件”，并输出标准化标签与特征，供统计建模直接使用。

## 2. `is_event` 判定标准

### 2.1 公式

`event_score = keyword_hit_count + min(duplicate_group_size, 3)`

`is_event = (event_score >= event_threshold)`，其中 `event_threshold = 2`。

### 2.2 预过滤

- 非金融噪声命中（如娱乐、综艺）直接判 `is_event=false`
- 弱中性披露（如“年度报告摘要”）且无事件关键词，判 `is_event=false`

### 2.3 证据字段

`evidence` 字段包含：
- 命中的关键词列表
- `score` 与 `threshold`
- 例如：`命中事件关键词: 印巴|空战; score=3; threshold=2`

`raw_event_candidates.csv` 强制落地字段：
- `event_score`
- `event_threshold`
- `rule_version`

### 2.4 本地 LLM 辅助判定口径

- 当前口径不是“纯规则驱动”，也不是“LLM 接管主判断”，而是：`规则优先 + 本地 LLM 辅助边界样本`
- 默认主判官仍是规则分数与硬过滤条件；LLM 只在小范围样本上参与辅助判断与摘要增强
- 当前本地 LLM 后端：`ollama`

LLM 触发条件（命中其一即可）：
- `borderline_score`：`event_score` 与阈值距离不超过 1 分
- `high_value_source`：来源属于高价值来源，如中国政府网、发改委、证监会、交易所、巨潮、财新、第一财经
- `industry_other`：规则输出 `industry_type=其他`
- `subject_default`：主体分类仍然模糊或默认
- `duplicate_cluster`：重复聚类规模较大，说明该文本具备发酵可能

LLM 后置锚点修正（防止强语义被弱化）：
- 地缘锚点：标题或正文命中 `中东/霍尔木兹/战事/停火/冲突/空战/印巴/克什米尔` 时，`event_subject_type` 优先保留 `地缘类`
- 消费景气锚点：命中 `轻工业/零售/餐饮/文旅/旅游/消费` 时，`industry_type` 优先保留 `消费`
- 科技政策锚点：命中 `无线电/卫星/通信/物联网/人工智能/具身智能` 时，`industry_type` 优先保留 `科技`
- 若 LLM 输出 `industry_type=其他`，但规则已有明确行业标签，则优先保留规则行业

LLM 允许做的事：
- 生成更稳定的 `event_name`
- 辅助修正 `event_subject_type`
- 辅助修正 `industry_type`
- 辅助补充 `sentiment`
- 为 `classification_evidence` 增加解释字段

LLM 不允许做的事：
- 覆盖强规则负例
- 直接决定收益标签
- 直接生成热度/强度数值

强规则负例不可被 LLM 翻盘的典型情形：
- `non_financial_noise`
- `generic_announcement_without_signal`
- 其他被硬过滤的非金融披露或噪声文本

`structured_events.csv` / 入库事件表中的 `classification_evidence` 需保留以下证据字段：
- `llm=1`
- `llm_backend=ollama`
- `llm_trigger=...`
- `llm_subject=...`
- `llm_industry=...`
- `llm_sentiment=...`

## 3. 四大分类维度（附件3对齐，枚举冻结）

- `event_subject_type`：`政策类 / 公司类 / 行业类 / 宏观类 / 地缘类`
- `duration_type`：`脉冲型 / 中期型 / 长尾型`
- `predictability_type`：`突发型 / 预披露型`
- `industry_type`：`军工 / 新能源 / 消费 / 科技 / 其他`

额外枚举：
- `impact_scope`：`全市场 / 行业 / 个股链条`

若规则输出超出枚举，自动回落到默认值，避免自由文本污染下游。

## 4. 特征打分规则（配置常量化）

- `heat_score`：来源权重 + 标题强词 + 重复报道加分（上限100）
- `intensity_score`：主体基准分 + 突发/冲击词/政策词加分（上限100）
- `impact_scope`：基于主体类型与全市场关键词规则判定

全部参数统一定义在：`src/capabilities/events/rules.py`，避免散落在业务代码中。

误判/漏判回流词典：
- 文件：`data/rule_feedback_keywords.csv`
- 规则：仅允许补充白名单维度关键词（subject/industry/predictability/duration），不改评分公式。

## 5. 正负例示例

### 正例（应识别为事件）

- 标题：`印巴在克什米尔爆发大规模空战`
- 输出：`is_event=true`，`event_subject_type=地缘类`，`industry_type=军工`，`duration_type=脉冲型`

### 负例（应过滤）

- 标题：`某综艺节目收视率创新高`
- 输出：`is_event=false`，`filter_reason=non_financial_noise`

## 6. 质量校验约束

`src/capabilities/quality/check.py` 强制校验：
- `is_event` 与 `event_score >= event_threshold` 一致性
- 枚举合法性（四大维度 + `impact_scope`）
- `rule_version` 一致性
- 关键正负样例回归通过

补充验收口径（规则版 vs 规则+LLM 版）：
- 同批输入上比较 `structured_events` 数量变化
- 抽查 LLM 新增事件是否具有真实金融意义
- 抽查 LLM 改写后的 `event_name / event_subject_type / industry_type / sentiment` 是否更稳定
- 单独监控 `industry_type=其他` 占比，防止 LLM 把模糊样本重新打回“其他”
