# is_event 规则改动前后对比报告（第3轮）

## 1. 本轮改动（task1_rules_v1 保持评分公式不变）

- 改动目标：修复“融资上市强信号豁免”带来的回归误判（`提示性公告` 被误判为事件）。
- 代码位置：
  - `src/capabilities/events/rules.py`
  - `src/capabilities/events/classify.py`
- 具体改动：
  - 新增 `LISTING_FINANCING_EXCLUSION_KEYWORDS`：
    - `提示性公告`、`进展公告`、`转股情况公告`、`法律意见书`、`补充法律意见书`
  - `listing_financing_strong` 从“命中强词”改为“命中强词且不命中排除词”。
  - 三个过滤器继续使用该强信号豁免，但由新逻辑控制：
    - `routine_announcement_without_signal`
    - `announcement_template_without_signal`
    - `generic_announcement_without_signal`

## 2. 判定口径（冻结版）

- 判定公式：`is_event = (event_score >= event_threshold)`
- 当前阈值：`event_threshold = 2`
- 评分主干：`event_score = 事件关键词命中数 + 去重组加分（上限）`
- 证据字段强制包含：
  - 命中词列表
  - `score`
  - `threshold`
  - `rule_version`
  - 四维命中线索（`subject/industry/predictability/duration`）

## 3. 对比结果

> 评估样本使用：`output/quality_sample_round3.csv`（14条）  
> 监督标签来源：`assistant_suggestion`（无人工标签时使用该列）

### 第3轮样本（14条）

- 改动前（无排除词）：
  - TP=4, TN=6, FP=1, FN=3
  - Accuracy=0.7143, Precision=0.8000, Recall=0.5714, F1=0.6667
- 改动后（加入排除词）：
  - TP=4, TN=7, FP=0, FN=3
  - Accuracy=0.7857, Precision=1.0000, Recall=0.5714, F1=0.7273

### 合并样本（round2+round3，共26条）

- 改动前：
  - TP=7, TN=12, FP=1, FN=6
  - Accuracy=0.7308, Precision=0.8750, Recall=0.5385, F1=0.6667
- 改动后：
  - TP=7, TN=13, FP=0, FN=6
  - Accuracy=0.7692, Precision=1.0000, Recall=0.5385, F1=0.7000

## 4. 关键样本变化（本轮仅 1 条发生翻转）

- 标题：`关于公司向不特定对象发行可转换公司债券的审核问询函回复及募集说明书等申请文件更新的提示性公告`
- 预期：`false`
- 改动前：`true`（`event_signal_detected`, score=2）
- 改动后：`false`（`routine_announcement_without_signal`, score=1）
- 结论：本轮改动成功消除了已知回归误判。

## 5. 产物与复核文件

- 分类重跑产物：
  - `output/raw_event_candidates.csv`
  - `output/structured_events.csv`
- 第3轮逐条前后对照：
  - `output/quality_sample_round3_compare.csv`

## 6. 当前残余问题（下一轮建议）

- 仍有 FN（漏判）集中在“融资/上市进程但文本极短、非模板强词不充分”的边界样本。
- 建议下一轮只做词典微调（不动阈值/公式）：
  - 从人工复核集中回流 3-5 个高价值词到白名单；
  - 保持排除词机制不变，避免 FP 回潮。
