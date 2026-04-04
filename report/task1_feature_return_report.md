# 任务1事件研究法（异常收益）报告

- run_id：20260404_120637
- 生成时间：2026-04-04 12:07:17
- 分析模式：event-study
- 事件-公司有效样本：0
- 分析输入行数：30
- 链接来源：event_company_links
- 基准：hs300（sina_index_fallback）
- token来源：missing
- 事件窗：1,3,5
- 时间预算(秒)：120
- 最大输入行数：30

## 一、总体CAR统计
- 暂无可计算样本。

## 二、分组CAR对比
- 分组字段：impact_scope
  - 无可用样本
- 分组字段：heat_bucket
  - 无可用样本
- 分组字段：intensity_bucket
  - 无可用样本

## 三、不可计算样本原因
- insufficient_event_window: 19
- event_outside_trade_dates: 11

## 四、说明
- 估计窗固定为[-120,-20]，事件窗为[t0,t0+w]。
- 若Tushare不可用，自动回退Sina行情接口并在报告中标记。
- 数据明细见：`/Users/tim/股市预测模型/output/task1_event_return_dataset.csv`