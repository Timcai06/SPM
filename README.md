# 股市预测模型

这是一个 **事件驱动量化研究平台**，不是赛题脚本集合。项目以 PostgreSQL 为中心，把原始文本、结构化事件、事件-公司关联和传播关系组织成可持续回填、可复算、可研究的数据底座。

## 当前架构

主路径已经收口到 `src/modules/...`：

- `src/modules/collectors/`：实时采集、历史采集、正文回填
- `src/modules/events/`：事件识别、结构化、归并、特征补齐
- `src/modules/companies/`：公司种子、画像、市场环境和辅助加载
- `src/modules/linking/`：事件-公司关联
- `src/modules/graph/`：公司关系与传播链
- `src/modules/analysis/`：事件研究、训练样本、负样本
- `src/modules/quality/`：校验、质量抽样、交付检查

`src/capabilities/...` 仍保留部分 legacy 实现，但已经退到桥接层，不再作为新增功能入口。

## 命令入口

公共入口现在按领域拆分：

- `src/cli/collect.py`
- `src/cli/events.py`
- `src/cli/linking.py`
- `src/cli/graph.py`
- `src/cli/research.py`
- `src/cli/quality.py`

推荐先看：

```bash
./atk help
python3 src/cli/collect.py --help
python3 src/cli/events.py --help
python3 src/cli/linking.py --help
python3 src/cli/graph.py --help
python3 src/cli/research.py --help
python3 src/cli/quality.py --help
make help
```

双机协作方案见：

- [DUAL_MACHINE_ARCHITECTURE.md](/Users/tim/股市预测模型/DUAL_MACHINE_ARCHITECTURE.md)

## 典型工作流

### 1. 采集与正文回填

发现新数据：

```bash
python3 src/cli/collect.py collect-history --db stock_event_mining --source cninfo-disclosure
```

回填已有巨潮 URL 的正文：

```bash
python3 src/cli/collect.py backfill-cninfo-fulltext --db stock_event_mining --start-date 2025-01-01 --end-date 2026-01-01
```

### 2. 事件标准化

一键事件归一化流程：

```bash
python3 src/cli/events.py run --limit 8 --with-analysis --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5
```

拆开执行：

```bash
python3 src/cli/events.py classify
python3 src/cli/events.py canonicalize
python3 src/cli/events.py canonical-load
```

### 3. 事件-公司关联

最小闭环：

```bash
python3 src/cli/linking.py run --db stock_event_mining --top-k 3 --min-score 0.35
```

只重跑链接：

```bash
python3 src/cli/linking.py link-events --db stock_event_mining --top-k 3 --min-score 0.35
```

### 4. 传播关系

```bash
python3 src/cli/graph.py run --db stock_event_mining --input output/seeds/company_relations_seed.csv --min-source-score 0.35 --min-propagation-score 0.20
```

### 5. 研究与样本

事件研究：

```bash
python3 src/cli/research.py feature --db stock_event_mining --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5
```

训练样本：

```bash
python3 src/cli/research.py train-samples --db stock_event_mining --min-link-score 0.35
```

负样本：

```bash
python3 src/cli/research.py build-negative-samples --db stock_event_mining --max-per-day 100
```

### 6. 质量检查

```bash
python3 src/cli/quality.py check
python3 src/cli/quality.py quality --sample-size 50
python3 src/cli/quality.py qa --db stock_event_mining
python3 src/cli/quality.py delivery-status --db stock_event_mining
```

## Makefile 入口

`atk` 是更短的领域入口：

```bash
./atk collect history HISTORY_SOURCE=cninfo-disclosure HISTORY_CNINFO_FULLTEXT=1
./atk events run DB=stock_event_mining LIMIT=20
./atk research feature TIME_BUDGET=300 MAX_ROWS=200
./atk quality db DB=stock_event_mining
```

常用目标：

```bash
make collect-history
make backfill-cninfo-fulltext
make events-run
make link-events
make graph-run
make research-feature
make research-train-samples
make research-negative-samples
make quality-summary
```

组合目标：

```bash
make research-base-pipeline
make full
make full-with-market
make go
```

## 数据库主表

数据库名是：

- `stock_event_mining`

当前主链表是：

- `raw_documents`
- `event_candidates`
- `structured_events`
- `canonical_event_clusters`
- `canonical_event_memberships`
- `companies`
- `company_profiles`
- `event_company_links`
- `company_relations`
- `event_propagation_edges`
- `security_features_daily`
- `security_forward_labels_daily`
- `event_research_samples`
- `control_research_samples`
- `etl_runs`
- `etl_run_steps`
- `dataset_versions`

完整分层说明见：

- [docs/database_model.md](/Users/tim/股市预测模型/docs/database_model.md)

命令行看表：

```bash
psql -d stock_event_mining
```

数据库摘要：

```bash
python3 src/cli/quality.py db-status --db stock_event_mining
make db-summary
```

## 目录约定

- `output/`：运行产物和导出，不作为源码事实源
- `report/`：按需生成的里程碑报告
- `sql/`：建表与只读视图
- `docs/`：操作说明、模板、架构文档

缓存和运行时目录：

- `.ruff_cache/`
- `.playwright-cli/`

它们都属于本地缓存/运行产物，不属于项目架构的一部分，可以删除，并应保持忽略状态。

## 当前边界

这个仓库当前聚焦：

1. 提升事件文本质量
2. 稳定事件结构化与事件-公司关联
3. 形成可研究、可训练的数据底座

它还不是一个完整的交易执行系统，也还没有覆盖真正的点时回测和组合执行层。
