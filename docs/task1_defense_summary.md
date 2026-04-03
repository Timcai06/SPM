# 任务1答辩摘要（可复现批次）

## 1. 目标与范围

- 目标：从多源文本中识别具金融影响的事件，完成标准化分类与量化特征提取，并输出可用于统计分析的结构化事件表。
- 本批次范围：任务1闭环能力（采集 -> 清洗 -> 判定 -> 分类 -> 特征 -> 入库 -> 质量评估 -> 事件研究法分析）。

## 2. 方法与实现要点

- 事件识别：`is_event = (event_score >= event_threshold)`，规则版本固定为 `task1_rules_v1`。
- 证据字段：每条候选输出命中词、score、threshold、rule_version、四维命中摘要（subject/industry/predictability/duration）。
- 分类体系：四大维度枚举冻结（主体、持续周期、可预测性、行业），避免自由文本污染下游。
- 特征提取：`heat_score`、`intensity_score`、`impact_scope`、`sentiment`、`subject_entities` 等字段入表。
- 误判回流：通过 `data/rule_feedback_keywords.csv` 增量补词，仅允许白名单维度关键词调整，不改评分公式。
- 采集增强：新增深交所停复牌细分源；采集报告新增失败分类（network/parse/empty_data/unknown）。

## 3. 结果与当前指标

- 结构化事件规模：本批次入库后 `structured_events = 135`。
- 事件-公司链接：`event_company_links = 186`（`top-k=5`）。
- 事件研究法（AR/CAR）：
  - 估计窗：`[-120,-20]`
  - 事件窗：`[0,1]`、`[0,3]`、`[0,5]`
  - 基准：HS300（当前回退数据源为 `sina_index_fallback`）
  - 可计算样本：`88`（已超过 30 样本目标）
- 对外产物：
  - `output/task1_quality_report.md`
  - `output/task1_feature_return_report.md`
  - `output/task1_event_return_dataset.csv`

## 4. 质量控制与稳定性

- 质量闭环：抽样 50 条生成人工复核模板，报告输出识别准确率、标签一致率、字段完整率、Top误判原因。
- 并发安全：写库路径使用数据库 advisory lock，避免并发写入导致 query failed 和脏数据。
- 数据鲁棒性：读取 CSV 时清洗 NUL 字节，避免 `_csv.Error: line contains NUL` 中断主流程。

## 5. 局限与后续计划

- 当前事件研究依赖可获得行情数据；若缺 Tushare Token，会回退到新浪接口，稳定性与覆盖受限。
- 建议下一步：
  - 启用 `TUSHARE_TOKEN` 提升交易日覆盖与一致性。
  - 扩充公司主数据和事件-公司映射覆盖，提高分组统计稳定性。
  - 固定周度批次复盘（规则词典回流 + 质量报告对比）。

