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
