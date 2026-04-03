# 任务1事件研究法（异常收益）报告

- run_id：RUN_FINAL_AFTER_EXPAND_001
- 生成时间：2026-04-03 11:50:36
- 分析模式：event-study
- 事件-公司有效样本：88
- 链接来源：event_company_links
- 基准：hs300（sina_index_fallback）
- 事件窗：1,3,5

## 一、总体CAR统计
- car_w1: 均值=2.3525%, t=2.600, 样本=88
- car_w3: 均值=4.6409%, t=2.758, 样本=71
- car_w5: 均值=3.7628%, t=2.452, 样本=66

## 二、分组CAR对比
- 分组字段：impact_scope
  - 全市场: 均值=1.2063%, t=1.162, 样本=32
  - 行业: 均值=7.9874%, t=2.675, 样本=30
  - 个股链条: 均值=-7.4705%, t=-4.819, 样本=4
- 分组字段：heat_bucket
  - mid: 均值=2.9911%, t=2.088, 样本=53
  - high: 均值=6.9088%, t=1.318, 样本=13
- 分组字段：intensity_bucket
  - high: 均值=4.2509%, t=2.634, 样本=62
  - mid: 均值=-3.8042%, t=-4.711, 样本=4

## 三、不可计算样本原因
- event_outside_trade_dates: 88
- insufficient_event_window: 10

## 四、说明
- 估计窗固定为[-120,-20]，事件窗为[t0,t0+w]。
- 若Tushare不可用，自动回退Sina行情接口并在报告中标记。
- 数据明细见：`/Users/tim/股市预测模型/output/task1_event_return_dataset.csv`