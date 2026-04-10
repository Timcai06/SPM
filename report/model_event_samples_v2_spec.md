# model_event_samples_v2 建模宽表说明

## 1. 文档目的

这份文档用于冻结当前项目的训练入口口径，让后续建模、实验和答辩都围绕同一套表结构开展。

当前建议的训练入口仍然是：

- `model_event_samples`：事件样本主表
- `model_non_event_samples`：负样本主表

辅助特征来源表：

- `company_stats`
- `event_company_links`
- `structured_events`
- `canonical_events`
- `event_propagation_links`

## 2. 当前数据状态

基于 2026-04-10 当前批次，训练底座已经达到下面这个规模：

- `company_stats`：78562
- `model_event_samples`：671
- `labeled_samples`：222
- `label_ratio`：33.08%
- `model_non_event_samples`：36377

这意味着现在已经具备：

- 事件正样本
- 事件收益标签
- 大规模非事件负样本
- 公司日频行为特征

## 3. 为什么仍然用 model_event_samples 做训练入口

当前阶段不建议再新建一张完全独立的训练主表，原因很直接：

- `model_event_samples` 已经把事件特征、链接特征、公司特征、标签汇总到单行样本
- 字段已经足够支撑第一版 LightGBM baseline
- 继续拆表会增加认知负担和维护成本

所以现阶段的做法是：

- 把 `model_event_samples` 视为正样本训练表
- 把 `model_non_event_samples` 视为负样本训练表
- 在训练脚本里按统一字段名拼接两者

## 4. model_event_samples 字段分层

### 4.1 主键与追踪字段

- `sample_key`
- `sample_run_id`
- `structured_event_id`
- `company_id`
- `canonical_event_id`
- `event_id`
- `event_date`
- `ts_code`
- `company_name`

作用：

- 唯一标识训练样本
- 支持回溯一条样本来自哪条事件、哪家公司、哪次批处理

### 4.2 事件特征

- `event_subject_type`
- `duration_type`
- `predictability_type`
- `event_industry_type`
- `sentiment`
- `heat_score`
- `intensity_score`
- `impact_scope`

作用：

- 表达事件本身的类别、持续性、可预测性、情绪、强度、影响范围

### 4.3 链接特征

- `link_type`
- `final_link_score`
- `company_industry_l1`
- `company_industry_l2`
- `concept_tags`

作用：

- 表达“事件为什么会连到这家公司”
- 是第一版替代图嵌入的重要关系特征

### 4.4 公司特征第一批

- `company_stat_date`
- `total_mv`
- `circ_mv`
- `pe_ttm`
- `pb`
- `turnover_rate`
- `volume_ratio`
- `trailing_return_20d`
- `volatility_20d`

作用：

- 这是最基础的控制变量层
- 用于控制规模、估值、流动性、短期行为偏差

### 4.5 公司特征第二批

这批是 2026-04-10 新补上的字段，全部来自现有日收益序列，不依赖新数据源：

- `trailing_return_5d`
- `trailing_return_60d`
- `volatility_5d`
- `volatility_60d`
- `up_days_20d`

作用：

- `trailing_return_5d`：更短期动量
- `trailing_return_60d`：更长周期趋势
- `volatility_5d`：短期风险
- `volatility_60d`：中期风险
- `up_days_20d`：过去 20 日上涨天数，近似情绪/强弱状态

### 4.6 标签字段

- `label_car_w1`
- `label_car_w3`
- `label_car_w5`
- `label_up_w1`
- `label_up_w3`
- `label_up_w5`
- `label_source`

作用：

- `car_w1 / w3 / w5` 是事件研究法生成的异常收益标签
- `up_*` 是二分类标签
- `label_source` 用于追踪标签来源

## 5. model_non_event_samples 的角色

这张表不是附属表，而是训练体系里必须保留的一半。

当前作用：

- 提供非事件交易日的负样本
- 支持二分类训练
- 支持事件样本与平凡样本对比

关键字段与 `model_event_samples` 尽量保持同构，便于训练时拼接：

- 公司基本信息
- 公司行为特征
- 第二批公司特征
- 未来收益标签

当前规模：

- `model_non_event_samples = 36377`

这意味着负样本规模已经不再是瓶颈。

## 6. 现阶段推荐的建模字段集合

第一版 LightGBM baseline 建议直接使用下面这组字段。

### 6.1 类别字段

- `event_subject_type`
- `duration_type`
- `predictability_type`
- `event_industry_type`
- `sentiment`
- `impact_scope`
- `link_type`
- `company_industry_l1`
- `company_industry_l2`

### 6.2 数值字段

- `heat_score`
- `intensity_score`
- `final_link_score`
- `total_mv`
- `circ_mv`
- `pe_ttm`
- `pb`
- `turnover_rate`
- `volume_ratio`
- `trailing_return_5d`
- `trailing_return_20d`
- `trailing_return_60d`
- `volatility_5d`
- `volatility_20d`
- `volatility_60d`
- `up_days_20d`

### 6.3 标签

优先级建议：

1. 排序/回归主标签：`label_car_w5`
2. 辅助回归标签：`label_car_w3`
3. 辅助分类标签：`label_up_w5`

原因：

- 当前任务已经把 `w1/w3/w5` 三个窗口都补齐了
- 题目本身更贴近周频持有，因此 `w5` 最适合作为主标签

## 7. 训练前的拼接建议

### 7.1 正样本

直接取：

- `model_event_samples`

过滤建议：

- `label_car_w5 IS NOT NULL`
- `final_link_score >= 0.35`

### 7.2 负样本

直接取：

- `model_non_event_samples`

负样本标签建议：

- 回归任务：直接使用 `label_ret_w5`
- 分类任务：直接使用 `label_up_w5`

### 7.3 时间切分

必须使用时间切分，禁止随机打乱：

- 训练集：更早时期
- 验证集：中间时期
- 测试集：更晚时期

## 8. 当前仍未进入宽表的内容

下面这些还不是当前版本的一部分：

- 图嵌入特征
- GNN 输出特征
- 更完整的估值/财务因子
- 行业指数相对收益
- 盘口/高频微结构特征

这不是缺陷，而是刻意分阶段推进。

当前目标是：

- 先把规则事件特征 + 公司特征 + 链接特征跑通 baseline
- 再逐步叠加图特征和更复杂因子

## 9. 给建模同学的直接使用建议

建模同学现在可以直接从这两张表开始：

- 正样本：`model_event_samples`
- 负样本：`model_non_event_samples`

第一版不需要再等：

- 新爬虫
- 新数据库
- GNN
- LLM 主推理链

直接先做：

1. `label_car_w5` 回归 baseline
2. `label_up_w5` 二分类 baseline
3. 时间切分验证
4. 查看 `final_link_score` 与新增公司特征是否带来增益

## 10. 当前结论

当前项目已经具备一版真正可训练的宽表体系：

- 事件表已结构化
- 公司特征已扩到两批
- 负样本已成规模
- 事件研究法标签已可同时覆盖 `w1/w3/w5`

因此，后续建模应当以这份口径为准，避免再反复变更训练输入定义。
