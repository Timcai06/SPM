# 股市预测模型

> 一个以 PostgreSQL 为中心的数据底座、以事件为主轴的研究型量化平台。  
> 当前系统已经完成从“脚本集合”到“可持续回填、可复算、可研究、可双机协作”的工程化转向。

## 摘要

本项目围绕 A 股公开信息流构建事件驱动研究基础设施，核心目标不是生成一次性的比赛结果，而是形成一套可长期迭代的数据与研究系统：

- 持续采集公告与资讯文本
- 将原始文本标准化为结构化事件
- 建立事件到公司的关联与传播关系
- 生成可研究、可训练、可追溯的数据集
- 支持双机协作：`M5 Pro` 负责数据库、开发、研究与训练，`Intel Mac` 负责长时间采集与正文回填

这套系统的核心约束是：**数据库是唯一事实源，Git 只同步代码，`output/` 只保存运行产物。**

---

## 一、项目全景

```mermaid
flowchart TD
    subgraph S["上游数据源"]
        A1["CNInfo"]
        A2["AKShare"]
        A3["公共资讯"]
    end

    subgraph P["主处理链路"]
        B["collectors<br/>采集 / 回填"]
        C["raw_documents"]
        D["events<br/>候选 / 结构化 / canonical"]
        E["linking"]
        F["graph"]
        G["analysis / research"]
        H["quality / delivery"]
    end

    I["run metadata<br/>etl_runs / etl_run_steps / dataset_versions"]

    A1 --> B
    A2 --> B
    A3 --> B
    B --> C --> D --> E --> F --> G --> H
    C -. lineage .-> I
    D -. lineage .-> I
    G -. lineage .-> I
```

### 当前定位

| 维度 | 当前状态 |
|---|---|
| 项目类型 | 事件驱动量化研究平台 |
| 主数据库 | `stock_event_mining` |
| 主代码分支 | `dev` |
| 运行分支 | `run` |
| 运行拓扑 | `M5 Pro (DB/研究)` + `Intel Mac (采集/回填)` |
| 主入口 | `./SPM` 与 `src/cli/*.py` |
| 当前阶段 | 数据底座与研究底座已经成形，当前正优先做厚 2025/2026 raw 层和强正文来源 |

---

## 二、当前项目状态

### 1. 数据库状态快照

更新时间：`2026-04-23`

| 表/主题 | 当前规模 |
|---|---:|
| `raw_documents` | 1,581,500 |
| `event_candidates` | 1,577,638 |
| `structured_events` | 370,135 |
| `canonical_event_clusters` | 106,760 |
| `canonical_event_memberships` | 332,660 |
| `company_relations` | 205 |
| `company_profiles` | 136 |
| `stock_daily_quotes` | 78,596 |
| `market_environment_daily` | 1,494 |
| `sentiment_propagation_daily` | 428 |
| `security_features_daily` | 78,770 |
| `security_forward_labels_daily` | 78,770 |
| `event_research_samples` | 538 |
| `control_research_samples` | 36,377 |
| `etl_runs` | 48 |
| `etl_run_steps` | 8 |

### 2. 2025-2026 raw 第一层快照

| 来源家族 | 行数 | 合格正文 | 强正文 |
|---|---:|---:|---:|
| 巨潮资讯网 | 517,743 | 201,952 | 201,021 |
| 深交所 | 2,097 | 206 | 0 |
| 上交所 | 1,279 | 202 | 0 |
| AKShare | 946 | 847 | 0 |
| 第一财经 | 655 | 42 | 0 |
| 中国政府网 | 383 | 370 | 303 |
| 中国证监会 | 198 | 178 | 160 |
| 财新网 | 186 | 66 | 0 |
| 东方财富 | 170 | 161 | 132 |
| 36氪 | 155 | 103 | 2 |
| 国家发改委 | 73 | 73 | 67 |
| 工信部 | 65 | 0 | 0 |

### 3. 2025-2026 巨潮正文回填进度

| 指标 | 数值 |
|---|---:|
| 2025-2026 巨潮历史公告总量 | 517,570 |
| 有效正文条数 | 211,701 |
| 有效正文覆盖率 | 40.90% |
| 命中 `12000` 字截断上限 | 17,903 |

```mermaid
pie title 2025-2026 巨潮正文覆盖率
    "已回填有效正文" : 211701
    "未回填或正文过短" : 305869
```

### 4. 当前工程判断

- **采集主链已补齐**：现有 adapter 都已进入 `collect-history` 主链
- **链路已跑通**：Intel 已能通过 TCP 直连 M5 上 PostgreSQL，并完成采集与正文回填写库
- **环境已分层**：M5 使用 `spm-m5pro` Conda 环境，Intel 使用 `.venv`
- **Git 结构已收敛**：只保留 `dev` 与 `run`
- **采集默认不走代理**：采集命令会做 direct-network preflight，不满足直连条件就直接退出
- **主要短板仍在来源均衡和正文覆盖**：不同来源的抓取策略由 source profile 集中管理，不再要求操作时人工区分

### 5. 现在推荐你只记两个采集命令

```bash
./SPM ingest full DB=stock_event_mining
./SPM status raw DB=stock_event_mining
```

这两个命令的职责是：

- `ingest full`：统一做 2025/2026 全量补数据。对正文型来源优先补正文，对其他来源优先补覆盖，对巨潮执行正文回填，并在末尾把 `symbol_or_subject` 规范到附件 2 的四类事件粗分类
- `status raw`：统一看 raw 层覆盖、正文质量、四类粗分类覆盖、以及距离目标行数还有多远

也就是说：

- 你不需要再自己区分“强正文/弱正文”或“该不该单独回填”
- 你不需要自己记每个来源的页数、并发和门槛
- 系统会把这些来源级规则集中在 `src/modules/collectors/domain/source_profiles.py`

---

## 三、系统架构

### 1. 代码分层

```mermaid
flowchart TD
    A["CLI<br/>src/cli/*.py"]
    B["jobs"]
    C["services"]
    D["domain"]
    E["adapters"]
    F["外部边界<br/>PostgreSQL / API / 文件系统"]
    G["pipelines"]
    H["runtime services<br/>run metadata / lineage"]

    A --> B --> C
    C --> D
    C --> E --> F
    G --> B
    G --> C
    H --> F
```

### 2. 领域模块

| 模块 | 角色 |
|---|---|
| `src/modules/collectors/` | 实时采集、历史采集、正文回填 |
| `src/modules/events/` | 候选事件、结构化事件、canonical 聚类 |
| `src/modules/companies/` | 公司主数据、画像、行业与市场补充数据 |
| `src/modules/linking/` | 事件-公司链接 |
| `src/modules/graph/` | 公司关系与传播链 |
| `src/modules/analysis/` | 事件研究、负样本、训练样本 |
| `src/modules/quality/` | 质量检查、存储治理、交付检查 |
| `src/modules/runtime/` | 运行元数据、数据集 lineage、数据库连接 |

### 3. 数据分层

| 层级 | 主表 |
|---|---|
| 原始事实层 | `raw_documents`, `stock_daily_quotes`, `market_environment_daily`, `sentiment_propagation_daily` |
| 事件标准化层 | `event_candidates`, `structured_events`, `canonical_event_clusters`, `canonical_event_memberships` |
| 公司与关系层 | `companies`, `company_profiles`, `event_company_links`, `company_relations`, `event_propagation_edges` |
| 研究样本层 | `security_features_daily`, `security_forward_labels_daily`, `event_research_samples`, `control_research_samples` |
| 治理层 | `etl_runs`, `etl_run_steps`, `dataset_versions` |

详细说明见 [docs/architecture/database-model.md](docs/architecture/database-model.md)。

---

## 四、双机协作体系

### 1. 当前正式协作模式

```mermaid
flowchart TD
    subgraph M5["M5 Pro"]
        A["dev 分支<br/>开发 / 清洗 / 研究 / 训练"]
        B["PostgreSQL 主库"]
    end

    subgraph Intel["Intel Mac"]
        C["run 分支<br/>采集 / 历史回填 / 正文回填"]
    end

    D["origin/dev"]
    E["origin/run"]

    A -->|本机读写| B
    C -->|TCP 直连| B
    A -->|git push| D
    A -->|发布运行代码| E
    C -->|git fetch / reset| E
```

### 2. 职责边界

| 机器 | 角色 | 环境 | 默认分支 |
|---|---|---|---|
| M5 Pro | PostgreSQL 主库、开发、清洗、研究、训练 | `conda activate spm-m5pro` | `dev` |
| Intel Mac | 采集、历史回填、正文回填、长时间运行任务 | `source .venv/bin/activate` | `run` |

### 3. Git 工作流

```mermaid
flowchart TD
    A["dev<br/>开发线"] --> B["提交功能与修复"]
    B --> C["验证通过"]
    C --> D["同步到 run"]
    D --> E["run<br/>Intel 运行线"]
    E --> F["采集 / 回填 / 长任务"]
```

实际约束是：

- `dev` 用于开发和结构调整
- `run` 用于 Intel 上的稳定执行
- Intel 不承担主开发职责
- 数据库不靠 Git 同步，仍只认 M5 上 PostgreSQL 主库

完整说明见 [docs/architecture/dual-machine-architecture.md](docs/architecture/dual-machine-architecture.md)。

---

## 五、运行入口

### 推荐入口

```bash
./SPM help
python3 src/cli/collect.py --help
python3 src/cli/events.py --help
python3 src/cli/linking.py --help
python3 src/cli/graph.py --help
python3 src/cli/research.py --help
python3 src/cli/quality.py --help
make help
```

### 入口优先级

日常使用建议固定成三层：

1. `./SPM ...` 给日常操作
2. `make ...` 给批量执行和自动化
3. `python3 src/cli/*.py ...` 给开发和调试

这样平时只需要记住少量高频任务组，不需要把底层实现命令全记住。

### 最常用命令

#### 用户入口

```bash
./SPM ingest history HISTORY_SOURCE=cninfo-disclosure DB=stock_event_mining
./SPM ingest history HISTORY_SOURCE=yicai-news DB=stock_event_mining HISTORY_START=2025-01-01 HISTORY_END=2026-04-23 HISTORY_MAX_PAGES=200 HISTORY_PAGE_SIZE=50 HISTORY_QUALITY_BODY_ONLY=1 HISTORY_MIN_CONTENT_LENGTH=300
./SPM ingest backfill DB=stock_event_mining CNINFO_BACKFILL_START=2025-01-01 CNINFO_BACKFILL_END=2026-01-01
./SPM event run DB=stock_event_mining LIMIT=8
./SPM research train DB=stock_event_mining
./SPM status db DB=stock_event_mining
./SPM status sources DB=stock_event_mining
```

#### 底层 CLI

```bash
python3 src/cli/collect.py collect-history --db stock_event_mining --source cninfo-disclosure
python3 src/cli/collect.py collect-history --db stock_event_mining --source yicai-news --start-date 2025-01-01 --end-date 2026-04-23 --max-pages 200 --page-size 50 --quality-body-only --min-content-length 300
python3 src/cli/collect.py backfill-cninfo-fulltext --db stock_event_mining --start-date 2025-01-01 --end-date 2026-12-31
```

#### 事件标准化

```bash
python3 src/cli/events.py run --db stock_event_mining --limit 8
python3 src/cli/events.py classify-pending --db stock_event_mining --batch-size 2000 --max-batches 1
```

#### 事件-公司关联与传播

```bash
python3 src/cli/linking.py run --db stock_event_mining --top-k 3 --min-score 0.35
python3 src/cli/graph.py run --db stock_event_mining --input output/seeds/company_relations_seed.csv
```

#### 研究与质量

```bash
python3 src/cli/research.py feature --db stock_event_mining --analysis-mode event-study --benchmark hs300
python3 src/cli/research.py train --db stock_event_mining --label-dataset output/event_return_dataset.csv
python3 src/cli/quality.py db --db stock_event_mining
python3 src/cli/quality.py summary --db stock_event_mining
python3 src/cli/quality.py sources --db stock_event_mining
```

---

## 六、环境策略

### M5 Pro

- 环境名：`spm-m5pro`
- 环境文件：[environment.m5pro.yml](environment.m5pro.yml)
- 适用范围：开发、数据处理、研究、深度学习

```bash
conda activate spm-m5pro
conda env update -n spm-m5pro -f environment.m5pro.yml
```

### Intel Mac

- 运行环境：仓库内 `.venv`
- 适用范围：采集、正文回填、入库
- 不强求全量研究依赖与 M5 完全同构

```bash
python3 -m venv .venv
source .venv/bin/activate
uv pip install requests aiohttp akshare pandas psycopg pdfplumber python-dotenv beautifulsoup4 lxml openpyxl html5lib
```

---

## 七、已解决的关键工程问题

| 问题 | 现象 | 当前处理 |
|---|---|---|
| 数据库连接写死本机 | Intel 只能靠 SSH tunnel 假装 localhost | `dsn_for()` 已支持环境变量与 DSN |
| Intel 上 `pdftotext` 依赖脆弱 | `poppler` 安装困难，正文回填卡死 | 先找 `pdftotext`，找不到自动回退 `pdfplumber` |
| 运行元数据建表权限问题 | `collector_runner` 不是 `etl_runs` owner，回填启动失败 | 若表已存在则跳过 DDL，只保留写入 run metadata |
| Intel 无法安装全量研究依赖 | `onnxruntime` 在 macOS 13 x86_64 无可用 wheel | Intel 改用“最小采集依赖”，研究依赖留给 M5 |
| 分支与 worktree 过多 | 开发线、运行线、旧分支混杂 | 收敛为 `dev` / `run` 两条分支 |

更多细节见 [docs/governance/known-issues.md](docs/governance/known-issues.md)。

---

## 八、当前限制

当前系统已经可以支持：

- 原始文本采集与历史补数
- 正文回填
- 事件结构化
- 事件-公司映射
- 传播图谱生成
- 基础事件研究与样本构建
- 运行元数据记录

但它还**不是**：

- 完整交易执行系统
- 高频回测平台
- 自动化生产调度平台
- 已完成所有点时研究数据补齐的成熟研究仓库

---

## 九、文档地图

```mermaid
flowchart TD
    A["docs/README.md<br/>文档中心"] --> B["overview/<br/>状态 / 技术总览"]
    A --> C["architecture/<br/>系统结构 / 数据模型"]
    A --> D["operations/<br/>运行手册 / 执行路线"]
    A --> E["governance/<br/>问题 / 存储 / 路线图"]
    A --> F["data/<br/>分类契约 / seed 模板"]
    A --> G["docs/architecture/dual-machine-architecture.md<br/>双机协作主说明"]
```

- 数据库模型：[docs/architecture/database-model.md](docs/architecture/database-model.md)
- 双机协作：[docs/architecture/dual-machine-architecture.md](docs/architecture/dual-machine-architecture.md)
- 存储治理：[docs/governance/storage-retention-policy.md](docs/governance/storage-retention-policy.md)
- 数据源扩展计划：[docs/data/source-expansion-plan.md](docs/data/source-expansion-plan.md)
- 原始来源能力矩阵：[docs/data/raw-source-capability-matrix.md](docs/data/raw-source-capability-matrix.md)

建议阅读顺序：

1. [docs/README.md](docs/README.md)
2. [docs/overview/project-status.md](docs/overview/project-status.md)
3. [docs/overview/tech-stack.md](docs/overview/tech-stack.md)
4. [docs/architecture/dual-machine-architecture.md](docs/architecture/dual-machine-architecture.md)
5. [docs/operations/runbook.md](docs/operations/runbook.md)
6. [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md)
7. [docs/architecture/database-model.md](docs/architecture/database-model.md)
8. [docs/governance/known-issues.md](docs/governance/known-issues.md)
9. [docs/governance/engineering-roadmap.md](docs/governance/engineering-roadmap.md)

---

## 十、结论

这不是一个“等所有功能补完再开始研究”的项目。  
它已经具备了可运行的工程内核：

- 有中心化数据库事实源
- 有双机协作模型
- 有可追踪的运行元数据
- 有稳定的 CLI 入口
- 有持续可提升的正文资产

接下来真正决定系统上限的，不再是“能不能跑”，而是：

1. 正文覆盖率能否继续上升  
2. 点时特征与标签能否继续补齐  
3. 研究样本与传播链是否足够稳定、可复算、可解释
