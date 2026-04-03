# 任务1质量评估报告

## 一、样本规模
- run_id：20260403_111121
- raw_event_candidates 条数：8
- structured_events 条数：5
- 人工抽样条数：8

## 二、识别准确率（人工复核）
- 当前尚未填写人工复核列 `manual_is_event`，暂无法计算准确率。
- 请在 `output/quality_sample.csv` 完成 20-50 条人工标注后重跑本脚本。

## 三、标签稳定性
- 同一 `raw_text_ref` 的四维标签一致率：100.00%

## 四、Top误判原因
- 当前人工复核中暂无误判，或尚未完成人工标注。

## 五、字段完整率（structured_events）
- `event_id` 完整率：100.00%
- `event_name` 完整率：100.00%
- `event_date` 完整率：100.00%
- `source` 完整率：100.00%
- `event_subject_type` 完整率：100.00%
- `duration_type` 完整率：100.00%
- `predictability_type` 完整率：100.00%
- `industry_type` 完整率：100.00%
- `sentiment` 完整率：100.00%
- `heat_score` 完整率：100.00%
- `intensity_score` 完整率：100.00%
- `impact_scope` 完整率：100.00%
- `event_summary` 完整率：100.00%
- `raw_text_ref` 完整率：100.00%

## 六、特征分布概览
- 平均 `heat_score`：66.80
- 平均 `intensity_score`：80.00

## 七、结论
- 本报告用于任务1质量闭环，重点关注识别准确率、标签稳定性、字段完整率。
- 建议每次规则版本升级后重跑本报告并对比历史结果。