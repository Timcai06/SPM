# 正式交付表补数优先级清单（v1）

## 1. 目标

本文把当前 **非 `int_` 正式表层** 的补数工作拆成明确执行顺序，避免一边改结构、一边补数据导致口径漂移。

适用表：

- `companies`
- `company_profiles`
- `stock_daily_quotes`
- `market_environment_daily`
- `company_relations`
- （联动验证）`event_company_links`、`model_event_samples`

约束原则：

1. 不先大改正式表结构。
2. 先补正式表缺失数据，再考虑 v2 新字段。
3. 每条补数链路都要能回流到现有 CLI/Makefile 入口。
4. 优先补能直接提升 **GNN 建图** 和 **LightGBM/XGBoost 特征质量** 的字段。

## 2. 当前快照（2026-04-16）

### 2.1 表级规模

| 表 | 当前行数 | 说明 |
| --- | ---: | --- |
| `companies` | 68 | 公司基础维表 |
| `company_profiles` | 68 | 公司画像快照，但大量字段为空 |
| `stock_daily_quotes` | 78589 | 个股日行情，覆盖 68 只股票，2020-02-19 ~ 2026-04-14 |
| `market_environment_daily` | 1492 | 市场环境日表 |
| `company_relations` | 41 | 公司关系边，全部来自手工 seed |
| `event_company_links` | 539 | 事件-公司边 |
| `model_event_samples` | 538 | 正样本训练表 |

### 2.2 字段完整度摘要

#### `company_profiles`

| 字段 | 已填充条数 / 68 | 状态 |
| --- | ---: | --- |
| `region` | 0 | 缺失 |
| `list_date` | 0 | 缺失 |
| `state_owned_flag` | 0 | 缺失 |
| `employees` | 0 | 缺失 |
| `total_shares` | 0 | 缺失 |
| `float_shares` | 0 | 缺失 |
| `core_products` | 68 | 已有 |

#### `stock_daily_quotes`

| 字段 | 已填充条数 / 78589 | 状态 |
| --- | ---: | --- |
| `open` | 78521 | 已填，但当前来自简化推断 |
| `high` | 78589 | 已填，但当前来自简化推断 |
| `low` | 78589 | 已填，但当前来自简化推断 |
| `amount` | 0 | 缺失 |
| `turnover_rate` | 0 | 缺失 |
| `adj_factor` | 0 | 缺失 |

#### `market_environment_daily`

| 字段 | 已填充条数 / 1492 | 状态 |
| --- | ---: | --- |
| `benchmark_code` | 1492 | 已有 |
| `northbound_net_flow` | 0 | 缺失 |
| `sector_hotness` | 1492 | 已有 |

#### `company_relations`

| 指标 | 当前值 | 状态 |
| --- | ---: | --- |
| 总边数 | 41 | 偏少 |
| `direction='directed'` | 2 | 太少 |
| `direction='undirected'` | 39 | 以弱标签边为主 |
| `is_manual_override=true` | 41 | 全量手工 seed |

## 3. 总体优先级

### P0：已完成
- 分类字典冻结
- 正式字段语义冻结
- DOCX 分类框架映射完成

### P1：必须先补
1. `company_profiles`
2. `stock_daily_quotes`

### P2：强烈建议补
3. `market_environment_daily`
4. `company_relations`

### P3：联动回归
5. `event_company_links`
6. `model_event_samples`

原因：

- `company_profiles` 和 `stock_daily_quotes` 直接决定节点属性与时序特征质量。
- `market_environment_daily` 决定事件发生背景。
- `company_relations` 决定图边质量。
- 上述四表补完后，`event_company_links` 与 `model_event_samples` 才值得重跑和复核。

## 4. 分表补数计划

---

## 4.1 `company_profiles`（第一优先级）

### 目标
把当前“从 `companies` 复制出的轻量快照”升级为可用于节点属性建模的正式画像表。

### 当前问题
当前 `load_company_profiles.py` 只是把 `companies` 的已有字段复制到 `company_profiles`，导致以下关键字段全空：

- `region`
- `list_date`
- `state_owned_flag`
- `employees`
- `total_shares`
- `float_shares`

### v1 必补字段

| 字段 | 作用 | 建议来源 |
| --- | --- | --- |
| `list_date` | 上市天数、成熟度 | Tushare 公司基础信息 |
| `region` | 地域属性、区域产业集群 | Tushare / 手工补充 / 公共源 |
| `state_owned_flag` | 国企属性 | 手工映射 + 公共资料 |
| `company_type` | 沪深主板/创业板/北交所等 | 由 `exchange` + 板块信息推断 |
| `employees` | 规模属性 | 财报 / 公共资料 |
| `total_shares` | 股本结构 | Tushare / 行情基础接口 |
| `float_shares` | 流通股本 | Tushare / 行情基础接口 |

### 推荐数据源
1. **第一来源**：Tushare 公司基础接口
2. **第二来源**：现有 `companies_seed.csv` / `companies_public.csv` / 手工 CSV
3. **第三来源**：公告或官网公开资料补录

### 现有代码触点
- `src/capabilities/storage/import_companies_tushare.py`
- `src/capabilities/storage/import_companies_public.py`
- `src/capabilities/storage/load_companies.py`
- `src/capabilities/storage/load_company_profiles.py`

### 推荐实施方式

#### 方案 A（推荐）
新增一个更完整的公司画像 seed，例如：
- `output/seeds/company_profiles_seed.csv`

然后让 `load_company_profiles.py`：
1. 先读 `companies` 作为基础维度
2. 再用 `company_profiles_seed.csv` 做字段覆盖
3. 最后 upsert 到 `company_profiles`

优点：
- 不破坏 `companies` 的轻量设计
- 便于答辩时区分“公司主数据”和“公司画像快照”

#### 方案 B（次优）
直接扩充 `companies_seed.csv`，再由 `load_company_profiles.py` 复制过去。

缺点：
- `companies` 会越来越重
- `company_profiles` 的快照意义会被弱化

### 验收标准
- `list_date` 填充率 > 90%
- `region` 填充率 > 80%
- `state_owned_flag` 填充率 > 70%
- `total_shares`、`float_shares` 填充率 > 80%

---

## 4.2 `stock_daily_quotes`（第一优先级）

### 目标
把当前“可算收益率的简化行情表”升级为可直接用于预测建模的正式日行情表。

### 当前问题
当前行情主要来自 `import_company_stats_sina.py` 生成的 `stock_daily_quotes.csv`，但该版本是简化 K 线：

- `open` 近似取前收
- `high` 近似取收盘
- `low` 近似取收盘
- `amount` 缺失
- `turnover_rate` 缺失
- `adj_factor` 缺失
- 涨跌停布尔值未真正计算

### v1 必补字段

| 字段 | 作用 | 建议来源 |
| --- | --- | --- |
| `open` | 标准 OHLC | Tushare / 本地行情 CSV |
| `high` | 标准 OHLC | Tushare / 本地行情 CSV |
| `low` | 标准 OHLC | Tushare / 本地行情 CSV |
| `amount` | 成交额 | Tushare / 本地行情 CSV |
| `turnover_rate` | 活跃度 | Tushare / 本地行情 CSV |
| `adj_factor` | 复权处理 | Tushare |
| `is_limit_up` | 极端交易特征 | 用涨跌幅 + 板块规则计算 |
| `is_limit_down` | 极端交易特征 | 用涨跌幅 + 板块规则计算 |

### 推荐数据源
1. **首选**：Tushare 日行情 + daily_basic + adj_factor
2. **备选**：本地标准行情 CSV（可复用 `docs/local_market_prices_template.csv`）
3. **兜底**：Sina 简化行情，仅保留连续性，不作为最终高质量交付源

### 现有代码触点
- `src/capabilities/storage/import_company_stats_sina.py`
- `src/capabilities/storage/import_company_stats_tushare.py`
- `src/capabilities/storage/import_company_stats_local.py`
- `src/capabilities/storage/load_company_stats.py`
- `docs/local_market_prices_template.csv`

### 当前实现缺口
当前代码里：
- `load_company_stats.py` **支持**通过 `--quotes-input` 加载 `stock_daily_quotes`
- 但真正会生成较完整 `quotes` 文件的只有 **Sina 简化版**
- `import_company_stats_tushare.py` 目前只生成 `company_stats.csv`，**不会生成完整 `stock_daily_quotes.csv`**

### 推荐实施方式

#### 方案 A（推荐）
扩展 `import_company_stats_tushare.py`，让它同时产出：
- `output/seeds/company_stats.csv`
- `output/seeds/stock_daily_quotes.csv`

这样可以直接复用现有：
- `python3 src/cli/task2.py load-company-stats --db stock_event_mining`

#### 方案 B（短期兜底）
使用本地行情 CSV：
1. 参考 `docs/local_market_prices_template.csv`
2. 扩充 `import_company_stats_local.py` 或新增本地 quotes 生成器
3. 再通过 `load_company_stats.py --quotes-input ...` 入库

### 验收标准
- `amount` 填充率 > 90%
- `turnover_rate` 填充率 > 90%
- `adj_factor` 填充率 > 90%
- `is_limit_up` / `is_limit_down` 不再全 0
- `open/high/low` 不再是“近似收盘”的简化值

---

## 4.3 `market_environment_daily`（第二优先级）

### 目标
把当前“由个股行情推导出的基础市场广度表”升级为正式市场背景因子表。

### 当前问题
当前 `load_market_environment.py` 主要根据：
- `stock_daily_quotes`
- 一个 HS300 基准
来生成：
- `index_return_1d`
- `market_turnover`
- `up_count / down_count`
- `limit_up_count / limit_down_count`
- `sector_hotness`

问题是：
- `northbound_net_flow` 全空
- 没有多指数并行
- 没有行业指数收益
- 没有融资融券、宏观利率等补充背景

### v1 必补字段

| 字段 | 作用 | 建议来源 |
| --- | --- | --- |
| `northbound_net_flow` | 风险偏好、外资行为 | Tushare / 东方财富 / 同花顺导出 |
| `index_return_1d` | 已有，保持 | 基准指数 |
| `index_return_5d` | 已有，保持 | 基准指数 |
| `index_volatility_20d` | 已有，保持 | 基准指数 |
| `market_turnover` | 已有，保持 | 两市成交额 |
| `up_count/down_count` | 已有，保持 | 全市场涨跌家数 |
| `limit_up_count/limit_down_count` | 已有，保持 | 全市场涨跌停统计 |
| `sector_hotness` | 已有，保持 | 行业热度 JSON |

### v1.5 建议补充但不强制改表
- 上证 / 深成 / 创业板 / 中证1000 多指数收益
- 行业指数收益
- 融资余额变化

### 现有代码触点
- `src/capabilities/storage/load_market_environment.py`
- `Makefile` 中 `market-env`

### 推荐实施方式
1. 保持 `market_environment_daily` 主表不改名。
2. 先把 `northbound_net_flow` 补实。
3. 如果需要多指数，不急着改主表，可先：
   - 追加到 `sector_hotness` 辅助结构；或
   - 等 v2 再新增专门指数表

### 验收标准
- `northbound_net_flow` 填充率 > 80%
- `market_turnover` 由真实两市成交额替代代理值
- `limit_up_count / limit_down_count` 与真实市场统计一致

---

## 4.4 `company_relations`（第二优先级）

### 目标
把当前“可答辩的一跳图传播 seed 边”升级为更稳定的正式图边表。

### 当前问题
当前 `company_relations`：
- 只有 41 条
- 全部来自手工 seed
- 关系类型偏粗
- `directed` 边只有 2 条

当前更像“演示图”，还不是“建模图”。

### v1 必补边类型

| 边类型 | 方向 | 优先级 | 用途 |
| --- | --- | --- | --- |
| 供应链/客户关系 | 有向 | 最高 | 最适合传播建模 |
| 持股/参股关系 | 有向 | 高 | 稳定公司关系 |
| 同一实控人 | 无向 | 高 | 集团/平台联动 |
| 同概念标签 | 无向 | 中 | 主题联动 |
| 同行业细分链 | 无向 | 中 | 行业扩散 |

### 数据来源建议
1. 手工 seed 扩充（短期最稳）
2. 公告、财报、招股书中抽取显式关系（中期）
3. 第三方产业链/股权关系表（长期）

### 现有代码触点
- `docs/task3_graph_design.md`
- `src/capabilities/storage/load_task3_relations.py`
- `src/capabilities/graph/propagate_event_links.py`
- `python3 src/cli/task3.py load-relations`
- `python3 src/cli/task3.py propagate`

### 推荐实施方式
1. 先扩 `output/seeds/company_relations_seed.csv`
2. 关系类型尽量收敛，不要自由发挥
3. 每条边都保留：
   - `relation_type`
   - `direction`
   - `relation_strength`
   - `evidence`
4. 优先让 `directed` 供应链边占比上来

### 验收标准
- 边数至少提升到 > 200
- `directed` 边占比显著提升
- 能覆盖当前 `event_company_links` 中的大部分高频公司

---

## 4.5 联动表：`event_company_links` 与 `model_event_samples`

这两张表不是本轮主补数对象，但必须作为回归验证层。

### 回归重点

#### `event_company_links`
补完 `company_profiles` / `company_relations` 后，需要复查：
- 直连事件数是否提升
- 覆盖公司数是否提升
- `direct_match` 与 `industry_match` 占比是否更合理

#### `model_event_samples`
补完行情和市场环境后，需要重跑：
- `company_stat_date`
- 公司统计字段
- 事件背景对齐字段
- 标签覆盖情况

### 目标
让 `model_event_samples` 从“可训练”提升到“特征解释更完整”。

## 5. 推荐执行顺序（具体到命令/实现）

### 阶段 1：公司画像补数
1. 扩充公司基础来源（Tushare + public + manual）
2. 升级 `load_company_profiles.py`
3. 执行：
   - `python3 src/cli/task2.py load-company-profiles --db stock_event_mining`

### 阶段 2：行情表补数
1. 扩展 Tushare 或本地行情导入，补齐完整 `stock_daily_quotes.csv`
2. 执行：
   - `python3 src/cli/task2.py import-company-stats --db stock_event_mining --source tushare --tushare-token-file .secrets/tushare_token.txt`
   - `python3 src/cli/task2.py load-company-stats --db stock_event_mining`

### 阶段 3：市场环境补数
1. 升级 `load_market_environment.py`
2. 补 `northbound_net_flow` 与真实市场成交额
3. 执行：
   - `python3 src/cli/task2.py load-market-environment --db stock_event_mining`

### 阶段 4：图边补数
1. 扩充 `company_relations_seed.csv`
2. 执行：
   - `python3 src/cli/task3.py load-relations --db stock_event_mining --input output/seeds/company_relations_seed.csv`
   - `python3 src/cli/task3.py propagate --db stock_event_mining`

### 阶段 5：样本回归
1. 重跑事件-公司链接
2. 重跑训练样本
3. 复查样本覆盖率和字段完整率

## 6. 建议的下一执行 lane

如果只选一个最值得马上开的 lane：

> **先做 `company_profiles + stock_daily_quotes` 这两张正式表的补数。**

理由：
- 一个补节点属性
- 一个补时序价格特征
- 直接提升 GNN 节点输入和传统预测模型特征质量
- 这两张表补完后，市场环境和图边补数会更稳

## 7. 结论

当前项目下一步不是再讨论“大改表结构”，而是按这个顺序进入补数执行：

> **先公司画像，再日行情；再市场环境，再公司关系；最后重跑链接与训练样本。**

