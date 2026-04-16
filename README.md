# 项目说明

这个目录实现了赛题任务 1 的一个最小可运行版本：把原始文本候选池转成标准化事件表，供统计同学直接接手。

## 当前实现范围

- main/dev tree 默认不保存 CSV（只保留源码/SQL/文档）
- 政府网采集结果：`output/sources/source_gov.csv`
- 发改委采集结果：`output/sources/source_ndrc.csv`
- 证监会采集结果：`output/sources/source_csrc.csv`
- 上交所公告采集结果：`output/sources/source_sse.csv`
- 巨潮公告采集结果：`output/sources/source_cninfo.csv`
- 深交所公告采集结果：`output/sources/source_szse.csv`
- 深交所停复牌公告采集结果：`output/sources/source_szse_suspension.csv`
- 第一财经新闻采集结果：`output/sources/source_yicai.csv`
- 东方财富行业资讯采集结果：`output/sources/source_eastmoney.csv`
- 36 氪股市快讯采集结果：`output/sources/source_36kr.csv`
- 财新网采集结果：`output/sources/source_caixin.csv`
- 工信部政策采集结果：`output/sources/source_miit.csv`
- 手工补录模板（运行时生成）：`output/seeds/manual_news.csv`
- 输出原始判定结果：`output/raw_event_candidates.csv`
- 输出标准化事件表：`output/structured_events.csv`
- 输出标准事件簇：`output/canonical_events.csv`
- 输出事件归并映射：`output/event_canonical_map.csv`
- 任务 1 采集入口：`src/capabilities/collectors/run.py`
- 任务 1 采集器目录：`src/capabilities/collectors/`
- 任务 1 分类与特征提取：`src/capabilities/events/classify.py`
- 任务 1 事件归并：`src/capabilities/events/canonicalize.py`
- 任务 1 冻结规则配置：`src/capabilities/events/rules.py`
- 任务 1 入库脚本：`src/capabilities/storage/load_task1.py`
- 任务 1 标准事件层入库脚本：`src/capabilities/storage/load_task1_canonical.py`
- 任务 1 校验脚本：`src/capabilities/quality/check.py`
- 任务 1 质量评估脚本：`src/capabilities/quality/quality_report.py`
- 任务 1 特征-收益初步分析：`src/capabilities/analysis/feature_return.py`
- 训练样本构建脚本：`src/capabilities/analysis/build_model_samples.py`
- 任务 1 一键总入口：`src/pipelines/task1.py`
- 任务 1 统一命令入口：`src/cli/task1.py`
- 任务 2 表结构：`sql/create_task2_tables.sql`
- 任务 1 规则说明（答辩版）：`docs/docs_task1_rulebook.md`
- 附录 2 来源目录（运行时生成）：`output/meta/appendix2_sources.csv`
- 公司导入脚本：`src/capabilities/storage/load_companies.py`
- 公司统计特征导入脚本：`src/capabilities/storage/load_company_stats.py`
- 事件-公司关联打分脚本：`src/capabilities/linking/link_events.py`
- 任务 2 一键入口：`src/pipelines/task2.py`
- 任务 2 统一命令入口：`src/cli/task2.py`
- 任务 3 图谱关系导入：`src/capabilities/storage/load_task3_relations.py`
- 任务 3 事件传播构建：`src/capabilities/graph/propagate_event_links.py`
- 任务 3 一键入口：`src/pipelines/task3.py`
- 任务 3 统一命令入口：`src/cli/task3.py`
- 当前综合进展报告：`report/project_progress_20260403.md`

## 已覆盖的任务 1 能力

- 数据字段标准化：`source`、`title`、`content`、`publish_time`、`url`、`symbol_or_subject`
- 候选文本去重键生成
- 非金融噪声过滤
- 事件二分类：`is_event`
- 核心标签分类：
  - `event_subject_type`
  - `duration_type`
  - `predictability_type`
  - `industry_type`
- 事件特征提取：
  - `event_date`
  - `event_summary`
  - `sentiment`
  - `heat_score`
  - `intensity_score`
  - `impact_scope`
  - `subject_entities`

## 运行方式

```bash
python3 src/cli/task1.py classify
python3 src/cli/task1.py canonicalize
python3 src/cli/task1.py canonical-load
python3 src/cli/task1.py check
```

推荐直接用一键总入口：

```bash
python3 src/cli/task1.py run --limit 8 --with-analysis --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5
```

这条命令会自动执行：
- 实时采集
- 清洗与事件判定
- 事件归并
- 标准事件层入库（`canonical_events` / `event_canonical_links`）
- CSV 输出
- PostgreSQL 入库
- 基本校验

任务 2 最小闭环：

```bash
python3 src/cli/task2.py run --db stock_event_mining --top-k 3 --min-score 0.35
```

这条命令会自动执行：
- 首批公司样本导入 `companies`
- 优先基于 `event_canonical_map.csv` 的标准事件簇做关联打分
- 把结果写入 `event_company_links`

导入公司统计特征并生成负样本：

```bash
python3 src/cli/task2.py import-company-stats --days 30 --tushare-token-file .secrets/tushare_token.txt
python3 src/cli/task2.py load-company-stats --db stock_event_mining
python3 src/cli/task2.py build-negative-samples --db stock_event_mining --max-per-day 100
```

如果没有 Tushare token，可直接改走 AKShare：

```bash
python3 src/cli/task2.py import-company-stats --db stock_event_mining --source auto --days 120 --max-symbols 300
python3 src/cli/task2.py load-company-stats --db stock_event_mining
```

说明：
- `source auto` 现在会按 `Tushare -> AKShare -> Sina` 自动回退。
- 无 token 环境下，通常会落到 `AKShare` 或 `Sina`。
- 这条路线会同时生成：
  - `output/seeds/company_stats.csv`
  - `output/seeds/stock_daily_quotes.csv`
- 完整的无 Tushare 流程参考：`docs/no_tushare_workflow.md`
- 如果你本地已有终端导出的完整行情 CSV，也可以直接：

```bash
python3 src/cli/task2.py import-company-stats-local --input docs/local_market_prices_template.csv
python3 src/cli/task2.py load-company-stats --db stock_event_mining
```

注意：
- 本地 CSV 中的 `ts_code` 需要已存在于 `companies` 表中。

导入公司画像快照（优先覆盖上市日期、地区、国企标签、员工、股本等字段）：

```bash
python3 src/cli/task2.py import-companies --output output/seeds/companies_a_share.csv --tushare-token-file .secrets/tushare_token.txt
python3 src/cli/task2.py load-company-profiles --db stock_event_mining --input output/seeds/companies_a_share.csv
```

无 Tushare token 时，可用公开源补画像 seed：

```bash
python3 src/cli/task2.py import-company-profiles --db stock_event_mining
python3 src/cli/task2.py load-company-profiles --db stock_event_mining --input output/seeds/company_profiles_seed.csv
```

说明：
- `load-company-profiles` 会优先读取你传入的画像 seed CSV。
- 若未传 `--input`，会自动尝试读取：
  - `output/seeds/company_profiles_seed.csv`
  - `output/seeds/companies_a_share.csv`
  - `output/seeds/companies_public.csv`
  - `output/seeds/companies_seed.csv`
- 手工补录可参考模板：`docs/company_profiles_seed_template.md`

生成市场环境日表，并可用 seed 覆盖北向资金/基准信息：

```bash
python3 src/cli/task2.py load-market-environment --db stock_event_mining
python3 src/cli/task2.py load-market-environment --db stock_event_mining --input output/seeds/market_environment_seed.csv
```

说明：
- 若 `stock_daily_quotes.amount` 已存在，`market_turnover` 优先使用真实成交额。
- 若传入 seed，可覆盖 `northbound_net_flow`、`benchmark_code`、`benchmark_name`。
- 手工补录可参考模板：`docs/market_environment_seed_template.md`

任务 3 准备闭环：

```bash
python3 src/cli/task3.py run --db stock_event_mining --input output/seeds/company_relations_seed.csv --min-source-score 0.35 --min-propagation-score 0.20
```

这条命令会自动执行：
- 把公司关系边导入 `company_relations`
- 优先基于标准事件簇聚合后的 `event_company_links` 构造一跳传播结果
- 把传播结果写入 `event_propagation_links`

单独导入公司关系边：

```bash
python3 src/cli/task3.py load-relations --db stock_event_mining --input output/seeds/company_relations_seed.csv
```

说明：
- seed 除了 `source_ts_code/target_ts_code/relation_type/relation_strength/direction` 外，
  还支持把 `data_source`、`confidence`、`effective_date` 等额外列写入 `evidence` JSON。
- 手工补录可参考模板：`docs/company_relations_seed_template.md`

默认情况下，`task1 classify` 在写出 CSV 后会继续把结果直接写入 PostgreSQL 的 `stock_event_mining` 数据库。

如果只想生成 CSV、不入库：

```bash
python3 src/cli/task1.py classify --skip-db-load
```

采集实时政府网数据并与样例/手工录入合并运行：

```bash
python3 src/cli/task1.py collect --limit 8
python3 src/capabilities/events/classify.py \
  --input output/sources/source_gov.csv \
  --input output/sources/source_ndrc.csv \
  --input output/sources/source_csrc.csv \
  --input output/sources/source_sse.csv \
  --input output/sources/source_cninfo.csv \
  --input output/sources/source_szse.csv \
  --input output/sources/source_szse_suspension.csv \
  --input output/sources/source_yicai.csv \
  --input output/sources/source_eastmoney.csv \
  --input output/sources/source_36kr.csv \
  --input output/sources/source_caixin.csv \
  --input output/sources/source_miit.csv \
  --input output/seeds/manual_news.csv
python3 src/cli/task1.py check
```

生成任务1质量抽样与质量报告：

```bash
python3 src/cli/task1.py quality --sample-size 50
```

生成任务1“特征与股价影响”初步统计报告：

```bash
python3 src/cli/task1.py feature --db stock_event_mining --min-link-score 0.35 --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5
```

如果你要限制分析耗时，推荐加：

```bash
python3 src/cli/task1.py feature --db stock_event_mining --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5 --time-budget-sec 240 --max-rows 200
```

构建模型训练样本表（`model_event_samples`）：

```bash
python3 src/cli/task1.py train-samples --db stock_event_mining --min-link-score 0.35
```

如需把事件研究的 `CAR` 标签并入训练样本（若你已生成 `output/task1_event_return_dataset.csv`）：

```bash
python3 src/cli/task1.py train-samples --db stock_event_mining --min-link-score 0.35 --label-dataset output/task1_event_return_dataset.csv
```

事件研究增强默认优先使用 `TUSHARE_TOKEN`（若存在），不可用时回退到新浪行情接口并在报告中标记数据源。

推荐把 token 放到本地文件（不入库）：

```bash
mkdir -p .secrets
printf '%s\n' '你的TushareToken' > .secrets/tushare_token.txt
chmod 600 .secrets/tushare_token.txt
python3 src/cli/task1.py feature --db stock_event_mining --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5 --tushare-token-file .secrets/tushare_token.txt
```

## 直观看表

命令行查询：

```bash
psql -d stock_event_mining
```

推荐直接使用 `pgAdmin4` 查看以下主表：

- `raw_documents`
- `structured_events`
- `label_dictionary`
- `companies`
- `company_profiles`
- `stock_daily_quotes`
- `market_environment_daily`
- `sentiment_propagation_daily`
- `event_company_links`
- `company_relations`
- `model_event_samples`

正式交付表状态检查：

```bash
python3 src/cli/task1.py delivery-status --db stock_event_mining
make delivery-status
```

说明：
- `delivery-status` 只读数据库，不写入、不清理数据。
- 输出中的 `BLOCK` 是当前正式交付表补数优先级。
- 所有 `int_` 开头的表属于内部加工层，不作为最终交付契约。

增加“易读表名层”（推荐）：

```bash
psql -d stock_event_mining -f sql/create_readable_views.sql
```

执行后会新增两类只读视图：
- 简洁英文视图：`events_structured`、`event_stock_links`、`stock_relations` 等
- 中文视图别名：`"结构化事件"`、`"事件公司关联"`、`"公司关系边"` 等

说明：
- 这一步不会改动原始表名，不会影响现有脚本
- 适合在 pgAdmin 中按中文名称直观看数

## 数据说明

首版现在支持两类输入（均在 run tree 运行时生成或维护）：

- 手工补录模板 CSV（`output/seeds/manual_news.csv`）
- 中国政府网实时抓取结果
- 国家发展改革委通知实时抓取结果
- 中国证监会要闻抓取结果
- 上交所最新公告抓取结果
- 巨潮资讯网最新公告抓取结果
- 深交所上市公司公告抓取结果
- 第一财经新闻列表抓取结果
- 东方财富行业资讯抓取结果
- 36 氪股市快讯抓取结果
- 财新网 mini 列表抓取结果
- 工信部政策列表抓取结果

## 目录与 CSV 规范（DB-First）

核心原则：`PostgreSQL 是唯一事实源（source of truth）`，CSV 只承担“输入种子 / 调试中间件 / 报告导出”的角色。

`main/dev worktree`
- 用途：只维护源码、SQL、文档，不存放 CSV。
- 适合放入 Git：是（代码与文档）。
- 约束：若出现 CSV，一律视为运行残留并清理。

`output/`（默认不追踪，偏运行态）
- 用途：流程运行产物（候选事件、结构化事件、归并映射、质量/分析导出）。
- 适合放入 Git：否（除“答辩快照”外）。
- 约束：优先写库；CSV 仅用于排查、抽样复核、对外演示导出。

`report/`（可追踪，面向答辩）
- 用途：里程碑报告、质量报告、事件研究结果摘要。
- 适合放入 Git：是（建议按批次保留关键版本）。
- 约束：报告引用的统计口径应可通过数据库复算，不以某个临时 CSV 为准。

工作流建议（与你当前双 worktree 一致）
1. `run worktree`：执行采集/分类/入库；`output/*.csv` 只做本地缓存，不作为协作主介质。  
2. `main/dev worktree`：只维护源码、SQL、文档（不保留 CSV）。  
3. 需要分享数据时：从数据库按 SQL 导出“受控快照 CSV”，放到 `report/` 对应批次目录并注明 `run_id`。  

什么时候必须看库而不是看 CSV
- 判断“是否真正入库成功”：以表行数和主键/唯一键冲突处理结果为准。
- 判断“全量/增量是否正确”：以数据库 `upsert` 后的统计为准，不以某个目录下 CSV 行数为准。
- 任务 2/3 联动：一律以库中 `structured_events / canonical_events / event_company_links / event_propagation_links` 为输入。

## 后续扩展方向

- 增加更多官方/财经来源采集器
- 增加更多来源与更细的行业词典
- 用模型补强规则分类和摘要质量
- 把输出接入任务 2 的事件-公司关联模块
- 把 run tree 的公司种子扩成真实全市场公司主数据
- 把 run tree 的关系种子扩成真实供应链/同概念/控股关系图
- 把一跳传播扩展到多跳传播与路径解释
