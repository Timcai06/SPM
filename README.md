# 项目说明

这个目录实现了赛题任务 1 的一个最小可运行版本：把原始文本候选池转成标准化事件表，供统计同学直接接手。

## 当前实现范围

- 演示输入：`data/demo_news.csv`
- 政府网采集结果：`data/source_gov.csv`
- 发改委采集结果：`data/source_ndrc.csv`
- 证监会采集结果：`data/source_csrc.csv`
- 上交所公告采集结果：`data/source_sse.csv`
- 巨潮公告采集结果：`data/source_cninfo.csv`
- 深交所公告采集结果：`data/source_szse.csv`
- 第一财经新闻采集结果：`data/source_yicai.csv`
- 东方财富行业资讯采集结果：`data/source_eastmoney.csv`
- 36 氪股市快讯采集结果：`data/source_36kr.csv`
- 财新网采集结果：`data/source_caixin.csv`
- 手工补录模板：`data/manual_news.csv`
- 输出原始判定结果：`output/raw_event_candidates.csv`
- 输出标准化事件表：`output/structured_events.csv`
- 任务 1 采集脚本：`src/task1_collect.py`
- 任务 1 采集器目录：`src/collectors/`
- 任务 1 分类与特征提取：`src/task1_classify.py`
- 任务 1 入库脚本：`src/task1_load_db.py`
- 任务 1 校验脚本：`src/task1_check.py`
- 任务 1 可视化页面：`src/task1_view.py`
- 任务 1 一键总入口：`src/task1_run.py`
- 任务 2 表结构：`sql/create_task2_tables.sql`
- 任务 1 规范说明：`docs_task1.md`
- 附录 2 来源目录：`data/appendix2_sources.csv`
- 公司导入脚本：`src/load_companies_to_postgres.py`
- 事件-公司关联打分脚本：`src/generate_event_company_links.py`
- 任务 2 一键入口：`src/run_task2_workflow.py`

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
python3 src/task1_classify.py
python3 src/task1_check.py
```

推荐直接用一键总入口：

```bash
python3 src/task1_run.py --limit 8
```

这条命令会自动执行：
- 实时采集
- 清洗与事件判定
- CSV 输出
- PostgreSQL 入库
- 基本校验

任务 2 最小闭环：

```bash
python3 src/run_task2_workflow.py --db stock_event_mining --top-k 3 --min-score 0.35
```

这条命令会自动执行：
- 首批公司样本导入 `companies`
- 对 `structured_events` 做最小关联打分
- 把结果写入 `event_company_links`

默认情况下，`task1_classify.py` 在写出 CSV 后会继续把结果直接写入 PostgreSQL 的 `stock_event_mining` 数据库。

如果只想生成 CSV、不入库：

```bash
python3 src/task1_classify.py --skip-db-load
```

采集实时政府网数据并与样例/手工录入合并运行：

```bash
python3 src/task1_collect.py --limit 8
python3 src/task1_classify.py \
  --input data/demo_news.csv \
  --input data/source_gov.csv \
  --input data/source_ndrc.csv \
  --input data/source_csrc.csv \
  --input data/source_sse.csv \
  --input data/source_cninfo.csv \
  --input data/source_szse.csv \
  --input data/source_yicai.csv \
  --input data/source_eastmoney.csv \
  --input data/source_36kr.csv \
  --input data/source_caixin.csv \
  --input data/manual_news.csv
python3 src/task1_check.py
```

## 直观看表

命令行查询：

```bash
psql -d stock_event_mining
```

本地网页查看：

```bash
python3 -m streamlit run src/task1_view.py
```

如果 `streamlit` 不在 PATH，可直接这样启动。

页面里现在也会显示任务 2 的两张表：
- `companies`
- `event_company_links`

## 数据说明

首版现在支持两类输入：

- 本地样例和手工补录 CSV
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

样例数据用于验证流程能跑通，包含：

- 正例：印巴空战、储能政策、重大合同、机器人技术突破
- 负例：娱乐新闻、无重大事项的年报摘要
- 重复样本：两条印巴空战近似报道

## 后续扩展方向

- 把样例 CSV 替换成真实爬虫/API 数据
- 增加更多官方/财经来源采集器
- 增加更多来源与更细的行业词典
- 用模型补强规则分类和摘要质量
- 把输出接入任务 2 的事件-公司关联模块
- 把 `companies_seed.csv` 扩成真实全市场公司主数据
