# 数据模型

## 基础概念

- `stock_event_mining` 是**数据库名**
- 下面这些名字才是你在 pgAdmin 里会看到的**主表名**

这轮重命名的目标只有一个：

**让你看到的表名，尽量直接表达业务角色。**

不再保留一层“物理表名”和一层“阅读视图名”的双重命名。

## 数据层次

### 1. 原始事实层

| 表名 | 角色 |
|---|---|
| `raw_documents` | 原始文本事实 |
| `stock_daily_quotes` | 个股日线市场事实 |
| `market_environment_daily` | 市场环境事实 |
| `sentiment_propagation_daily` | 舆情/传播环境事实 |

### 2. 事件标准化层

| 表名 | 角色 |
|---|---|
| `event_candidates` | 候选事件筛选结果 |
| `structured_events` | 结构化事件主表 |
| `canonical_event_clusters` | canonical 事件簇 |
| `canonical_event_memberships` | 结构化事件到事件簇映射 |

### 3. 证券与关系层

| 表名 | 角色 |
|---|---|
| `companies` | 证券主数据 |
| `company_profiles` | 证券/公司画像快照 |
| `event_company_links` | 事件到证券映射 |
| `company_relations` | 证券关系图边 |
| `event_propagation_edges` | 传播后的事件影响边 |

### 4. 研究与样本层

| 表名 | 角色 |
|---|---|
| `security_features_daily` | 日度证券市场特征面板（点时可见） |
| `security_forward_labels_daily` | 日度证券未来收益标签面板 |
| `event_research_samples` | 事件研究样本 |
| `control_research_samples` | 非事件对照样本 |

### 5. 运行治理层

| 表名 | 角色 |
|---|---|
| `etl_runs` | 顶层运行记录 |
| `etl_run_steps` | step 级 lineage |
| `dataset_versions` | 数据集产物注册 |

### 6. Staging 层

| 表名 | 角色 |
|---|---|
| `stg_event_candidates` | 事件候选装载缓冲 |
| `stg_structured_events` | 结构化事件装载缓冲 |

## 当前最重要的结构判断

### 已经比较清楚的链路

主链现在是：

`raw_documents -> event_candidates -> structured_events -> event_company_links`

这条链已经是你数据库的核心。

### 还不够干净的地方

当前最需要继续做实的，是市场与基本面层：

- `security_features_daily`
- `security_forward_labels_daily`

现在这两张表已经完成职责拆分：

1. `security_features_daily` 只保留点时可见特征
2. `security_forward_labels_daily` 只保留未来收益标签

下一步不再是拆表，而是补齐字段覆盖率。

## 这轮重命名的边界

这轮只做：

1. 把最混乱的 `int_* / stage / sample` 名字改成正常表名
2. 删除多余的 readability views
3. 统一 README / SQL / 代码里的同一套说法

这轮不做：

1. 大规模业务逻辑改写
2. point-in-time 证券主数据设计
3. 市场与基本面字段补齐

## 下一轮更值得做的事

1. 补齐 `security_features_daily`
2. 设计 point-in-time 证券主数据
3. 做市场与基本面字段覆盖率治理
