# 双机协作架构说明

这份文档只解决一件事：

**让 Intel 老 Mac 负责采集，M5 Pro 负责 PostgreSQL、开发、数据清洗和深度学习，并把外接 SSD 纳入架构。**

## 结论

推荐方案是：

- **M5 Pro**
  - PostgreSQL 主库
  - 代码开发
  - 数据清洗
  - `events / linking / graph / research / quality`
  - PyTorch / notebook / 实验
- **Intel 老 Mac**
  - 长时间运行采集和正文回填
  - `collect history`
  - `collect backfill-cninfo`
- **外接 SSD**
  - 承载 PostgreSQL data directory 或数据库备份
  - 作为高容量、可迁移的存储层
  - **只能挂载给实际运行 PostgreSQL 的那台机器**

**两台电脑公用一个代码库是不够的。**

**一块外接硬盘也不等于两台电脑同时共用数据库。**

还必须同时满足：

1. 两台机器各自有同一个 Git 仓库副本
2. 两台机器都能访问 **同一个 PostgreSQL 主库**
3. 采集和研究使用不同的本地环境与密钥
4. `output/` 不作为事实源，只作为运行产物目录
5. 运行和产物要写 `etl_runs / etl_run_steps / dataset_versions`

这套方案当前的正式连接方式是：

- **Intel Mac 通过 TCP 直连 M5 Pro 上的 PostgreSQL**
- **不依赖 SSH tunnel**
- **连接参数通过环境变量控制，不再写死 localhost**

## 推荐拓扑

```mermaid
flowchart LR
  A["Intel Mac<br/>采集 / 回填 / 长时间任务"] -->|SQL 写入| B["PostgreSQL on M5 Pro"]
  C["M5 Pro<br/>开发 / 清洗 / PyTorch / 研究"] -->|本机 SQL 读写| B
  E["外接 SSD<br/>PostgreSQL data directory 或备份"] --- B
  A -->|git pull / push| D["Git Remote"]
  C -->|git pull / push| D
```

## 这份设计真正解决的是什么

这份方案不是为了把两台机器“都利用起来”这么简单。

它真正解决的是四个基础设施问题：

1. **单一事实源**
   - 所有结构化数据最终只认一个 PostgreSQL 主库
2. **角色隔离**
   - Intel Mac 跑网络重、I/O 重、长时间任务
   - M5 Pro 跑数据库、本地分析、训练和交互式开发
3. **运行可追踪**
   - 任务运行记录写入 `etl_runs / etl_run_steps / dataset_versions`
4. **产物边界清晰**
   - `output/` 是运行产物，不是跨机器事实源

如果不先把这四件事讲清楚，后面不管是加 Ray、加定时调度，还是加更多机器，都会先撞上数据一致性和故障恢复问题。

## Infra 视角的分层

从基础设施视角看，这套系统应该拆成 4 层，而不是只看“哪台机器跑什么命令”。

### 1. Control Plane

负责决定“谁做什么、何时做、失败后怎么认定”：

- Git 仓库
- CLI 入口和 Makefile / `SPM`
- 任务参数
- `etl_runs / etl_run_steps`
- 后续如果引入 Ray，那么 Ray Head 也属于 control plane

### 2. Data Plane

负责真正搬运和写入数据：

- Intel Mac 上的采集请求
- CNInfo / AKShare 等上游访问
- PostgreSQL 读写
- 批量 flush / upsert
- 外接 SSD 上的数据库数据目录或备份

### 3. Compute Plane

负责 CPU/GPU 计算和本地处理：

- Intel Mac 上的抓取、正文提取、轻清洗
- M5 Pro 上的 `events / linking / graph / research`
- M5 Pro 上的 pandas / polars / DuckDB / PyTorch / notebook

### 4. Artifact Plane

负责临时产物和可交付物：

- `output/`
- `report/`
- 导出的 csv / parquet
- 数据集版本登记

这四层分开之后，很多判断会立刻变清楚：

- Git 只能解决 control plane 的代码同步
- PostgreSQL 是 data plane 的核心
- Ray 如果要引入，本质上是在增强 compute plane 和一部分 control plane
- `output/` 绝对不应该反向承担 data plane 的职责

## 关键设计原则

### 1. 先统一状态，再增加并行

先把数据库、运行记录、输入输出边界统一，再谈 Ray、并行、分布式调度。

否则只会得到“并发地制造不一致”。

### 2. 采集任务优先做到幂等和可重跑

抓取、回填、补正文这类任务必须允许：

- 中断
- 重试
- 分片
- 重跑

否则第二台机器只会放大失败面。

### 3. 写库路径要尽量收敛

多机环境下，最危险的不是“算得慢”，而是“多个执行器同时写，语义不清楚”。

所以数据库写入路径要明确：

- 谁能写
- 写哪些表
- 失败怎么回滚
- 重跑是否会重复写

### 4. 控制面不要依赖会随时睡眠的机器

这条对后续 Ray 很关键。

如果你把调度大脑、数据库主库、交互开发环境都堆在 M5 Pro 上，那么 M5 一睡眠，整套系统的 control plane 就断了。

开发时可以这么做，长期常驻生产不建议。

## 故障域

双机系统不能只看“拓扑对不对”，还要看“哪台机器挂了会影响什么”。

### 故障域 A：M5 Pro 不可用

影响：

- PostgreSQL 主库不可用
- Intel Mac 无法继续入库
- M5 本地研究、训练、后处理全部停止
- 如果未来 Ray Head 也在 M5，整个调度平面也会停止

结论：

- 方案 A 的最大弱点不是性能，而是可用性
- 只要主库在 M5，Intel Mac 就不是严格意义上的 24/7 采集机

### 故障域 B：Intel Mac 不可用

影响：

- 新采集和回填停止
- 已写入主库的数据和研究能力不受影响

结论：

- 这是一个可接受的从属节点故障
- 说明 Intel Mac 适合作为 worker / collector，而不是 stateful primary

### 故障域 C：外接 SSD 不可用

影响取决于 SSD 的用途：

- 如果承载 PostgreSQL data directory，则主库直接受影响
- 如果只承载备份和导出，则主库可以继续跑，但恢复能力下降

结论：

- 生产主库的数据目录放外接 SSD 可以做
- 但必须接受“线缆 / 供电 / 盘盒 / Hub”本身也是故障源

### 故障域 D：局域网链路不稳定

影响：

- Intel Mac 抓到了数据但无法及时写库
- 远程任务成功率下降
- 如果未来 Ray 跨机器调度，也会直接受网络波动影响

结论：

- 局域网稳定性在双机系统里属于一等公民，不是附属条件

## 产物位置与数据局部性

多机系统里，文件“放在哪台机器可见”必须明确，否则 `dataset_versions` 只会记录一堆另一台机器打不开的绝对路径。

### 哪些东西必须中心化

- PostgreSQL 主库
- schema 和运行元数据
- 备份策略

### 哪些东西可以本地化

- `output/` 目录
- 临时 CSV
- 采集过程日志
- Notebook 中间文件

### 哪些东西要显式区分“本地路径”和“共享产物”

- 导出 csv / parquet
- 报告
- 模型文件
- 特征快照

更稳妥的做法是未来给产物元数据补两个字段：

- `producer_host`
- `storage_uri` 或可迁移的逻辑路径

否则多机后很容易出现：

- 记录里写着“产物已生成”
- 但产物只存在 Intel Mac 本地
- M5 Pro 上的研究流程无法直接消费

## 当前代码现实意味着什么

从仓库当前实现看，这套系统已经具备“双机协作”基础，但还没有进入“分布式计算框架主导”的阶段。

原因主要有三点：

1. 采集和回填当前主要是单机线程并发
   - `history_collect_service.py`
   - `cninfo_fulltext_backfill_service.py`
2. 数据库连接虽然支持远程 DSN / `PGHOST`
   - 但默认仍回退到 `127.0.0.1`
3. 很多写路径有全局写锁语义
   - 这对安全是好事
   - 但对未来多机并发写入会形成天然串行化边界

这意味着你现在最成熟的系统形态是：

- **双机 ETL**
- **单主库**
- **远程 TCP 连库**
- **单机内并发**

而不是：

- **全链路分布式计算**
- **多执行器自由写库**
- **控制面和计算面完全解耦**

## Ray 的引入边界

Ray 可以引入，但不应该一上来就接管整条流水线。

正确问题不是“能不能把两台机器都变成 Ray 节点”，而是“哪一段任务已经满足分布式执行前提”。

### 适合先接入 Ray 的任务

- URL 抓取
- 页面解析
- 正文抽取
- 轻量文本清洗
- 明确按 symbol / URL / 日期片段切分的任务

这些任务的共同点是：

- 输入切片天然存在
- 单任务状态小
- 失败可以重试
- 结果可以批量汇总后再入库

### 暂时不适合直接交给 Ray 的任务

- `events / linking / graph / research` 全链路主流程
- 大量依赖数据库全表扫描和集中写入的步骤
- 需要严格串行语义的写任务
- 交互式 notebook / 训练实验

这些任务还没到“把代码包上 `@ray.remote` 就有收益”的阶段。

### 如果未来引入 Ray，推荐的边界

推荐只让 Ray 负责：

- **remote fetch / parse / clean**
- **分布式执行无状态子任务**
- **把结果汇总回单点 writer**

不推荐让多个 Ray worker 直接自由写主库。

更稳妥的模式是：

1. Ray worker 拉取和清洗
2. 结果返回给 Head 或 writer actor
3. 由单独 writer 统一批量写 PostgreSQL
4. `etl_runs / etl_run_steps` 继续保留在主库中做审计

这样 Ray 只增强计算与调度，不破坏当前的状态边界。

## 当前阶段与下一阶段

### 当前阶段：双机协作数据底座

目标是：

- Intel Mac 稳定抓取和回填
- M5 Pro 稳定做后处理和研究
- PostgreSQL 保持唯一事实源
- 运行可审计、任务可重跑

### 下一阶段：受控引入分布式调度

只有当下面这些条件已经满足，Ray 才值得引入：

- 分片语义稳定
- 幂等性清楚
- 失败重试策略清楚
- 写库路径已经收敛
- 两台机器环境一致性可维护

### 更长期阶段：真正的常驻控制面

如果你未来真的要做 24/7：

- 数据库主库不应依赖会睡眠的交互开发机
- 调度头节点也不应依赖会睡眠的交互开发机
- M5 更适合作为高性能研究终端，而不是长期唯一控制面

这时再考虑：

- PostgreSQL 迁到 always-on 机器
- Ray Head 迁到 always-on 机器
- M5 作为高性能 client / researcher

## 外接 SSD 的正确用法

### 可以做什么

外接 SSD 适合承担：

1. PostgreSQL 的 `data directory`
2. `pg_dump` / `pg_basebackup` 备份
3. 大型 parquet / csv 导出
4. 长期归档的 `output/` 日志与报告

### 不能怎么用

不应该这样用：

- 两台电脑都把同一个外接盘挂上，然后直接读写同一个 PostgreSQL 数据目录
- 把 PostgreSQL 停掉后，频繁在两台机器之间来回插拔作为“共享数据库”
- 通过普通文件共享把 PostgreSQL 数据目录暴露给另一台机器直接访问

原因很简单：

- PostgreSQL 需要**单机独占**数据目录
- 文件锁和 WAL 语义不是给“双机共享盘”设计的
- 这样做很容易损坏数据库

### 正确模式

正确模式只有一种：

- **外接 SSD 连接到其中一台机器**
- **那台机器运行 PostgreSQL**
- **另一台机器通过网络连 PostgreSQL**

## 你这套场景下的两个可行拓扑

### 方案 A：PostgreSQL 仍在 M5 Pro，外接 SSD 也接在 M5 Pro

```mermaid
flowchart LR
  A["Intel Mac<br/>always-on crawler"] -->|SQL 写入| B["PostgreSQL on M5 Pro"]
  C["M5 Pro<br/>research / training"] -->|本机 SQL 读写| B
  D["外接 SSD"] --- B
```

优点：

- 研究和训练离数据库最近
- M5 Pro 本地分析最顺手
- 数据、代码、训练都集中

缺点：

- M5 Pro 睡眠或关机时，Intel Mac 无法继续写库
- Intel Mac 不能真正 24/7 持续采集入库，除非 M5 Pro 常开

### 方案 B：PostgreSQL 在 Intel Mac，外接 SSD 也接在 Intel Mac

```mermaid
flowchart LR
  A["Intel Mac<br/>always-on crawler + PostgreSQL"] -->|本机写入| B["PostgreSQL on Intel Mac"]
  D["外接 SSD"] --- B
  C["M5 Pro<br/>research / training"] -->|SQL 读写| B
```

优点：

- Intel Mac 可以长期常驻
- 爬虫和数据库都在 always-on 机器上
- 更适合持续回填和长时抓取

缺点：

- M5 Pro 做研究时是远程访问数据库
- 训练和分析的数据库延迟略高
- 你原本想把 PostgreSQL 放在 M5 Pro，这个方案和原偏好相反

## 针对你当前偏好的判断

你现在同时提出了两个偏好：

1. **PostgreSQL 放在 M5 Pro**
2. **Intel Mac 常驻，长期跑爬虫和回填**

这两个偏好天然有一点冲突。

如果 PostgreSQL 真放在 M5 Pro：

- Intel Mac 能否持续写库，取决于 M5 Pro 是否常开

所以要做一个明确选择：

- 如果你更重视**研究和训练便利**，选方案 A
- 如果你更重视**常驻采集稳定性**，选方案 B

按你当前描述，我的工程判断是：

- **短期**：先用方案 A，保持 PostgreSQL 在 M5 Pro
- **长期**：如果 Intel Mac 真的承担常驻采集，再切到方案 B

## Git 在双机里负责什么

Git 负责的是：

- 代码状态
- SQL 迁移脚本
- 文档
- Makefile / SPM

Git **不负责**：

- PostgreSQL 中的数据内容
- 运行中的数据库状态
- 外接 SSD 上的数据库文件状态

更直接地说：

- Git 管理 **code state**
- PostgreSQL 管理 **data state**
- `etl_runs / etl_run_steps / dataset_versions` 管理 **run state**

所以你说“使用 Git 管理两台电脑的状态”，准确做法应该是：

- 用 Git 管理两台电脑的**代码状态**
- 用数据库和备份策略管理**数据状态**
- 用 run metadata 管理**运行状态**

## 角色分工

### Intel 老 Mac

只做网络重、I/O 重、长时运行的任务：

- `./SPM collect history ...`
- `./SPM collect backfill-cninfo ...`
- 未来的市场数据抓取
- 定时任务或守护进程

不建议在 Intel Mac 上做：

- 结构化事件主流程
- 大量 SQL 分析
- pandas / polars 深度清洗
- PyTorch 训练

### M5 Pro

做数据库、开发和研究：

- PostgreSQL 主库
- 代码开发与重构
- `./SPM events run ...`
- `./SPM linking run ...`
- `./SPM graph run ...`
- `./SPM research feature ...`
- `./SPM research train-samples ...`
- pandas / polars / DuckDB
- PyTorch / MPS

## 数据和代码分别怎么同步

```mermaid
flowchart TD
  A["Git 仓库"] --> B["Intel Mac 本地代码副本"]
  A --> C["M5 Pro 本地代码副本"]
  D["PostgreSQL 主库 on M5 Pro"] --> B
  D --> C
  E["output/ 日志和导出"] --> B
  E --> C
```

### Git 负责什么

Git 只负责：

- `src/`
- `sql/`
- `docs/`
- `Makefile`
- `SPM`

### PostgreSQL 负责什么

PostgreSQL 是唯一事实源，负责：

- `raw_documents`
- `event_candidates`
- `structured_events`
- `event_company_links`
- `event_propagation_edges`
- `security_features_daily`
- `security_forward_labels_daily`
- `event_research_samples`
- `control_research_samples`
- `etl_runs / etl_run_steps / dataset_versions`

### `output/` 负责什么

`output/` 只负责运行产物：

- 日志
- 中间导出
- 临时 CSV
- 报告

它不是 source of truth，不应该作为双机同步核心。

## 为什么“只共用一个代码库”不够

因为代码同步不能解决这几个问题：

1. **数据一致性**
   - 两台机器如果各写各的本地库，数据会分叉
2. **环境差异**
   - Intel Mac 适合采集
   - M5 Pro 适合分析和训练
3. **密钥与代理**
   - 采集机和研究机不应该共享同一套本地 secrets
4. **运行可审计性**
   - 同一个代码版本，也可能在不同机器产出不同结果

所以正确做法是：

- **代码通过 Git 同步**
- **数据通过 PostgreSQL 主库集中**
- **运行通过 run metadata 记录**
- **数据库通过外接 SSD + 备份策略保障**

## 推荐的运行流程

```mermaid
sequenceDiagram
  participant Intel as Intel Mac
  participant DB as PostgreSQL on M5 Pro
  participant M5 as M5 Pro

  Intel->>DB: collect history / backfill raw documents
  M5->>DB: classify / canonicalize / link / propagate
  M5->>DB: build features / labels / research samples
  M5->>M5: run pandas / polars / PyTorch experiments
```

## 当前仓库里的连接约定

代码连接层现在已经支持双机环境，不再要求“必须是本机数据库”。

主连接入口是：

- `src/modules/runtime/adapters/db.py`

当前优先级是：

1. `STOCK_EVENT_MINING_DSN`
2. `PGHOST / PGPORT / PGUSER / PGPASSWORD`
3. 本机默认回退：`host=127.0.0.1 port=5432 user=tim`

这意味着：

- 在 M5 Pro 本机，什么都不配也能继续跑
- 在 Intel Mac 上，只要设置 PostgreSQL 环境变量，就能直连 M5 Pro
- 后续如果改成 Tailscale / WireGuard，代码层不需要再改

推荐优先使用标准 PostgreSQL 环境变量，而不是把密码和地址散落在脚本里。

### Intel Mac 推荐环境变量

```bash
export PGHOST=192.168.43.14
export PGPORT=5432
export PGUSER=collector_runner
export PGPASSWORD='强密码'
export PGDATABASE=stock_event_mining
```

如果你更想用单一 DSN，也可以：

```bash
export STOCK_EVENT_MINING_DSN='postgresql://collector_runner:强密码@192.168.43.14:5432/stock_event_mining'
```

但从可维护性上，优先还是推荐 `PGHOST` 这组环境变量。

## PostgreSQL 放在 M5 Pro 时的关键技术点

### 1. 网络访问

M5 Pro 上的 PostgreSQL 需要允许 Intel Mac 访问。

最少要处理：

- `listen_addresses`
- `pg_hba.conf`
- M5 Pro 防火墙
- 固定局域网 IP 或稳定主机名

建议：

- 只允许局域网内 Intel Mac 的 IP
- 不开放到公网

一个可执行的方向是：

```conf
# postgresql.conf
listen_addresses = '*'
port = 5432
```

```conf
# pg_hba.conf
host    stock_event_mining    collector_runner    192.168.43.0/24    scram-sha-256
host    stock_event_mining    research_runner     192.168.43.0/24    scram-sha-256
```

如果你已经知道 Intel Mac 的固定 IP，更推荐写成单 IP，而不是整个网段。

### 2. 认证

为 Intel Mac 单独建数据库用户，不要直接复用开发主用户。

建议至少区分：

- `collector_runner`
- `research_runner`

这样未来更容易审计和限权。

最小示例：

```sql
create role collector_runner login password '强密码';
grant connect on database stock_event_mining to collector_runner;
grant usage on schema public to collector_runner;
grant select, insert, update, delete on all tables in schema public to collector_runner;
grant usage, select on all sequences in schema public to collector_runner;
```

如果你明确要把 Intel 机器限制为“只做采集”，后续还可以继续把它的权限缩到只覆盖采集链路涉及的表。

### 3. 外接 SSD 文件系统和连接方式

建议：

- 文件系统：`APFS`
- 连接方式：优先直连 `USB-C / Thunderbolt`
- 不要用 `exFAT` 承载 PostgreSQL data directory
- 不要通过不稳定 Hub 长期挂主库

### 4. M5 Pro 关机问题

如果 PostgreSQL 在 M5 Pro 上：

- M5 Pro 睡眠或关机时
- Intel Mac 的采集写入就会失败

这不是 bug，是架构事实。

所以你需要二选一：

1. 爬虫运行窗口内保持 M5 Pro 常开
2. 未来把 PostgreSQL 迁到独立常驻机器

当前阶段，先接受第 1 条就够了。

## 环境建议

### Intel Mac

保留最小运行环境：

- Python
- Git
- PostgreSQL client
- 采集依赖
- `.secrets/` 中仅采集相关 token

### M5 Pro

保留完整研究环境：

- Python
- Git
- PostgreSQL client/server
- 数据处理库
- Jupyter / notebook
- PyTorch
- 本地开发工具链

## 外接 SSD 上建议放什么

如果你决定把外接 SSD 纳入主架构，建议目录大致这样分：

```text
ExternalSSD/
  postgres/
    data/
  backups/
    pg_dump/
    basebackup/
  exports/
    parquet/
    csv/
  archive/
    output-history/
```

其中：

- `postgres/data/` 只能在**运行 PostgreSQL 的那台机器**上使用
- `backups/` 可以跨机读取
- `exports/` 可以跨机共享

## 目录和文件约定

两台机器都保留同一个 repo 结构，但本地内容职责不同：

- `src/`、`sql/`、`docs/`：都同步
- `.secrets/`：各自本地维护，不进 Git
- `output/`：各自产生日志，不当作同步主对象
- `env/`：各自机器本地环境

## 最新双机协作系统

当前推荐的正式系统是：

- **M5 Pro**
  - PostgreSQL 主库
  - 主开发机
  - 数据清洗
  - `events / linking / graph / research / quality`
  - 深度学习和实验
- **Intel Mac**
  - 第二工作机
  - 历史采集
  - 巨潮正文回填
  - 长时间、I/O 重、可中断重跑的任务
- **连接方式**
  - Intel 通过局域网 **TCP 直连** M5 上的 PostgreSQL
  - 不使用 SSH tunnel
  - 连接参数由环境变量控制
- **同步边界**
  - Git 同步代码
  - PostgreSQL 同步数据
  - `output/` 不作为双机同步事实源

这套系统里，Intel 的目标不是“复制一台研究机”，而是“成为专职采集机”。

## 从零落地步骤

下面这部分假设：

- 你的 **M5 Pro** 已经有当前仓库和主数据库
- 你的 **Intel Mac** 还是一台空机器，尚未安装代码和运行环境
- 你希望采用 **TCP 直连 PostgreSQL**

### 第 1 步：先在 M5 Pro 上准备 PostgreSQL

#### 1.1 确认 PostgreSQL 正常运行

```bash
psql -d stock_event_mining -c "select current_database(), current_user, now();"
python3 src/cli/quality.py db-status --db stock_event_mining
```

#### 1.2 找到 M5 Pro 的局域网 IP

常见 Wi-Fi 网卡：

```bash
ipconfig getifaddr en0
```

如果你走的是有线网卡，再看 `en1` 或实际接口名。

后面文档里用 `192.168.43.14` 只是示例，你应该替换成你的实际 IP。

#### 1.3 修改 `postgresql.conf`

至少保证：

```conf
listen_addresses = '*'
port = 5432
```

#### 1.4 修改 `pg_hba.conf`

如果你知道 Intel Mac 的固定 IP，优先只放行这一台机器。示例：

```conf
host    stock_event_mining    collector_runner    192.168.43.20/32    scram-sha-256
host    stock_event_mining    research_runner     192.168.43.14/32    scram-sha-256
```

如果 Intel 的 IP 暂时不固定，也可以先放一个局域网网段：

```conf
host    stock_event_mining    collector_runner    192.168.43.0/24    scram-sha-256
host    stock_event_mining    research_runner     192.168.43.0/24    scram-sha-256
```

但长期还是推荐收紧到单 IP。

#### 1.5 创建 Intel 专用数据库用户

```sql
create role collector_runner login password '强密码';
grant connect on database stock_event_mining to collector_runner;
```

切到业务库后继续授权：

```sql
\c stock_event_mining
grant usage on schema public to collector_runner;
grant select, insert, update, delete on all tables in schema public to collector_runner;
grant usage, select on all sequences in schema public to collector_runner;
```

如果后面你要进一步收紧权限，再把它限制到采集链路涉及的表。

#### 1.6 重启 PostgreSQL

如果你是 Homebrew 安装，常见是：

```bash
brew services restart postgresql@16
```

如果你本机装的是别的版本，把 `@16` 换成对应版本。

#### 1.7 检查 M5 Pro 防火墙

你要保证 Intel Mac 到 M5 Pro 的 `5432/TCP` 在局域网内可达，但不要暴露到公网。

### 第 2 步：在 Intel Mac 上准备基础工具

#### 2.1 安装 Xcode Command Line Tools

```bash
xcode-select --install
```

#### 2.2 安装 Homebrew

如果 Intel 上还没有：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2.3 安装基础软件

```bash
brew install git python postgresql@16
```

确认一下：

```bash
git --version
python3 --version
psql --version
```

### 第 3 步：在 Intel Mac 上拉代码

示例目录：

```bash
mkdir -p ~/work
cd ~/work
git clone <你的仓库地址> 股市预测模型
cd 股市预测模型
```

先确认入口可见：

```bash
./SPM help
make help
```

### 第 4 步：在 Intel Mac 上创建 Python 环境

#### 4.1 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

#### 4.2 安装依赖

优先尝试完整安装：

```bash
pip install -r requirements.txt
```

如果 Intel 老机器因为 `torch` 或其他重依赖导致失败，再退回“采集最小集”路线。但优先还是先试完整依赖，因为仓库里的采集链路可能会共用一部分公共包。

#### 4.3 验证采集 CLI

```bash
python3 src/cli/collect.py --help
```

如果这一步起不来，不要急着配数据库，先把 Intel 本机 Python 环境修好。

### 第 5 步：在 Intel Mac 上配置 TCP 数据库连接

推荐使用 PostgreSQL 标准环境变量：

```bash
export PGHOST=192.168.43.14
export PGPORT=5432
export PGUSER=collector_runner
export PGPASSWORD='强密码'
export PGDATABASE=stock_event_mining
```

也可以改用单一 DSN：

```bash
export STOCK_EVENT_MINING_DSN='postgresql://collector_runner:强密码@192.168.43.14:5432/stock_event_mining'
```

但默认仍推荐 `PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE`。

#### 5.1 先测试 psql 直连

```bash
psql -d stock_event_mining -c "select current_database(), current_user, now();"
```

这一步不通时，优先排查：

- `PGHOST` 是否填对
- M5 Pro 的局域网 IP 是否变化
- `postgresql.conf` 的 `listen_addresses`
- `pg_hba.conf`
- M5 Pro 防火墙
- Intel 和 M5 是否处在同一个局域网

### 第 6 步：在 Intel Mac 上准备本地 secrets

仓库里明确规定：

- `.secrets/` 是本地输入
- 不进 Git
- 不应整目录跨机复制

先建目录：

```bash
mkdir -p .secrets
```

如果后面要跑需要 token 的链路，例如 Tushare，再按需放：

```bash
printf '%s' '你的tushare_token' > .secrets/tushare_token.txt
chmod 600 .secrets/tushare_token.txt
```

如果当前 Intel 只做 `cninfo-disclosure` 历史公告和正文回填，通常可以先不依赖这类 token。

### 第 7 步：先做最小双机联通验证

不要一上来就跑大任务。先验证最小闭环：

#### 7.1 看帮助

```bash
python3 src/cli/collect.py --help
```

#### 7.2 跑一个小规模历史采集

```bash
python3 src/cli/collect.py collect-history \
  --db stock_event_mining \
  --source cninfo-disclosure \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --max-symbols 3 \
  --limit-per-symbol 5 \
  --workers 2 \
  --db-flush-every 20
```

#### 7.3 回到 M5 Pro 上查库

```bash
psql -d stock_event_mining -c "select count(*) from raw_documents;"
psql -d stock_event_mining -c \"select source, max(created_at) from raw_documents group by 1 order by 2 desc limit 5;\"
```

如果这里能看到新数据，就说明：

- Intel 本机 Python 环境没问题
- Intel 到 M5 的 TCP 连库没问题
- 采集链路能把数据写进主库

### 第 8 步：Intel Mac 的正式职责

Intel Mac 以后只建议跑采集与回填。

#### 8.1 历史采集

最小版本：

```bash
./SPM collect history DB=stock_event_mining HISTORY_SOURCE=cninfo-disclosure
```

常用版本：

```bash
./SPM collect history \
  DB=stock_event_mining \
  HISTORY_SOURCE=cninfo-disclosure \
  HISTORY_START=2023-01-01 \
  HISTORY_END=2025-12-31 \
  HISTORY_MAX_SYMBOLS=200 \
  HISTORY_LIMIT_PER_SYMBOL=100 \
  HISTORY_WORKERS=4 \
  HISTORY_CNINFO_FULLTEXT=1
```

#### 8.2 巨潮正文回填

最小版本：

```bash
./SPM collect backfill-cninfo \
  DB=stock_event_mining \
  CNINFO_BACKFILL_START=2025-01-01 \
  CNINFO_BACKFILL_END=2026-01-01
```

常用版本：

```bash
./SPM collect backfill-cninfo \
  DB=stock_event_mining \
  CNINFO_BACKFILL_START=2025-01-01 \
  CNINFO_BACKFILL_END=2026-01-01 \
  CNINFO_BACKFILL_MAX_ROWS=5000 \
  CNINFO_BACKFILL_WORKERS=8 \
  CNINFO_BACKFILL_DB_FLUSH_EVERY=100
```

### 第 9 步：M5 Pro 的正式职责

Intel 把数据写进 `raw_documents` 后，M5 Pro 负责后处理和研究。

#### 9.1 事件标准化和链接

```bash
./SPM events run DB=stock_event_mining LIMIT=20
./SPM linking run DB=stock_event_mining TOP_K=3 MIN_SCORE=0.35
./SPM graph run DB=stock_event_mining MIN_SCORE=0.35
```

#### 9.2 研究与质量检查

```bash
./SPM research feature DB=stock_event_mining TIME_BUDGET=300 MAX_ROWS=200
./SPM quality db DB=stock_event_mining
```

如果你想更保守一些，也可以拆开跑：

```bash
python3 src/cli/events.py classify-pending --db stock_event_mining --batch-size 3000 --max-batches 5
python3 src/cli/linking.py link-events --db stock_event_mining --top-k 3 --min-score 0.35
python3 src/cli/quality.py db-status --db stock_event_mining
```

## 日常启动顺序

### M5 Pro

```bash
brew services start postgresql@16
cd /Users/tim/股市预测模型
python3 src/cli/quality.py db-status --db stock_event_mining
```

### Intel Mac

```bash
cd ~/work/股市预测模型
source .venv/bin/activate
export PGHOST=192.168.43.14
export PGPORT=5432
export PGUSER=collector_runner
export PGPASSWORD='强密码'
export PGDATABASE=stock_event_mining
./SPM collect history DB=stock_event_mining HISTORY_SOURCE=cninfo-disclosure
```

## 运行命令建议

### Intel Mac

先配置数据库连接：

```bash
export PGHOST=192.168.43.14
export PGPORT=5432
export PGUSER=collector_runner
export PGPASSWORD='强密码'
export PGDATABASE=stock_event_mining
```

然后只跑采集和回填：

```bash
./SPM collect history DB=stock_event_mining HISTORY_SOURCE=cninfo-disclosure
./SPM collect backfill-cninfo DB=stock_event_mining CNINFO_BACKFILL_START=2025-01-01 CNINFO_BACKFILL_END=2026-01-01
```

### M5 Pro

M5 Pro 本机通常不需要额外配置 DSN，直接跑后处理、研究和训练即可：

```bash
./SPM events run DB=stock_event_mining LIMIT=20
./SPM linking run DB=stock_event_mining TOP_K=3 MIN_SCORE=0.35
./SPM graph run DB=stock_event_mining MIN_SCORE=0.35
./SPM research feature DB=stock_event_mining TIME_BUDGET=300 MAX_ROWS=200
```

### 不推荐的运行方式

不推荐在 Intel Mac 上直接跑整条研究流水线，例如：

- `make full`
- `make go`
- `make research-base-pipeline`

原因是这些组合目标默认把采集、分类、链接、研究混在一起，更适合单机串行执行，不适合你现在的双机分工。

同样也不推荐：

- 在 Intel Mac 上再维护一个独立 PostgreSQL 本地库并与 M5 并行写入
- 依赖 `output/` 目录做双机同步
- 把 M5 的 `.secrets/` 整目录复制到 Intel
- 让 Intel 直接承担 `events / linking / graph / research` 主链

## 最小落地方案

如果你现在就要开始双机协作，最小方案是：

1. M5 Pro 上运行 PostgreSQL
2. 外接 SSD 连接到 M5 Pro，用于 PostgreSQL data directory 或数据库备份
3. 两台机器都 clone 同一个 Git 仓库
4. Intel Mac 只跑 `collect`
5. M5 Pro 跑其余所有命令
6. 所有事实数据只写进 M5 Pro 的 `stock_event_mining`
7. `output/` 不同步，只保留本机日志

进一步展开成具体步骤就是：

1. 在 M5 Pro 上启动 PostgreSQL，并允许 Intel Mac 局域网 TCP 访问
2. 在 M5 Pro 上创建 `collector_runner`
3. 在 Intel Mac 上配置 `PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE`
4. 在 Intel Mac 上只运行 `collect history` 和 `backfill-cninfo`
5. 在 M5 Pro 上运行 `events / linking / graph / research / quality`
6. 两台机器都通过 Git 同步 `src/ / sql/ / docs/ / Makefile / SPM`
7. 两台机器都不要把 `output/` 当作双机同步主对象

## 故障排查顺序

如果 Intel 侧跑不起来，建议按这个顺序排查：

1. `python3 src/cli/collect.py --help`
   先确认 Intel 本机 Python 环境没坏
2. `psql -d stock_event_mining -c "select now();"`
   再确认 TCP 连库没坏
3. 检查 `PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE`
4. 检查 M5 Pro 的局域网 IP 是否变化
5. 检查 M5 的 `listen_addresses`
6. 检查 `pg_hba.conf`
7. 检查 M5 防火墙
8. 再去看具体采集任务本身是否被上游网站限流或拒绝

## 后续可以再补的东西

当前这份已经足够支撑双机落地，后续再补的内容主要是：

- Intel 开机自启采集任务
- LaunchAgent / cron / 守护进程
- 局域网 DNS / 固定 IP
- 数据库备份与恢复
- Tailscale / WireGuard 等跨网方案
- 运行资源监控

## 一句话

**可以两台机器共用一个代码库，但这只是最低条件，不是完整方案。**

完整方案应该是：

- **Git 统一代码**
- **一台机器统一 PostgreSQL**
- **外接 SSD 承载数据库存储或备份**
- **Intel Mac 专职采集**
- **M5 Pro 专职研究和训练**
- **运行产物和审计写进数据库，而不是靠 `output/` 互拷**
