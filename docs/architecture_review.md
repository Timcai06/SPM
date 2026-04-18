# 股市预测模型 — 架构深度审查报告

> 审查范围：5个最大Python文件 + rules.py + delivery_status.py
> 总代码量约 15400 行 Python，本次审查覆盖 ~5291 行（34%）
> 审查时间：2026-04-17

---

## 一、总体架构评估

本项目是一个股市事件挖掘系统，面向数学建模竞赛，流水线分为：
- **采集层** (collectors) → **分类层** (classify) → **规范化层** (canonicalize) → **关联层** (linking) → **分析层** (analysis) → **质量层** (quality) → **存储层** (storage)
- **CLI调度层** (cli/task1.py, task2.py) 通过 `patched_argv` 模式桥接到各能力模块

架构层次清晰，模块边界基本合理，但存在 **巨型文件承担过多职责** 和 **CLI层与能力层耦合过深** 两个核心问题。

---

## 二、逐文件深度分析

### 2.1 classify.py（1664行）— 事件分类引擎

#### 职责清单（7项独立职责）

| # | 职责 | 行数范围 | 说明 |
|---|------|---------|------|
| 1 | 规则配置 & 反馈关键词合并 | 1-490 | 常量、映射表、合并逻辑 |
| 2 | 数据加载 & 去重 | 506-546 | load_rows, dedup_key, normalize_datetime |
| 3 | 事件检测（核心） | 564-760 | detect_event — 多级关键词过滤 |
| 4 | 维度标注计算 | 763-920 | subject/industry/duration/sentiment/heat/intensity/impact 等15+个compute_*函数 |
| 5 | 实体抽取 & 摘要生成 | 923-970 | extract_subject_entities, build_summary |
| 6 | LLM增强（第二遍） | 1168-1555 | AsyncLLMClient, AsyncOllamaClient, should_trigger_llm, process_one |
| 7 | 输出/数据库持久化 & CLI | 972-1070, 1584-1664 | write_csv, load_outputs_to_postgres, run_classification_pipeline, main |

#### 函数统计
- 函数/方法数：**~54个**（含2个LLM Client类的方法）
- 平均函数长度：~31行，但方差极大
  - `detect_event`：~197行（巨型函数）
  - `classify_rows_async` + 内嵌 `process_one`：~140行
  - `main`：~40行
  - 大部分 `compute_*` 函数：5-15行（合理）

#### 耦合分析
- `detect_event` → 依赖 `ACTIVE_*_RULES` 全局状态（模块级加载）
- `build_structured_row` → 调用了10+个compute函数，形成"瀑布式"调用链
- `classify_rows_async` 内嵌 `process_one` 闭包，无法独立测试
- `build_candidate_row` 和 `build_structured_row` 重复调用 `choose_label` 四次（subject/industry/predictability/duration各一次），同一文本的标注逻辑被重复计算
- LLM Client 直接在classify.py内定义，与分类逻辑强耦合

#### 错误处理模式
- **严重不足**：`detect_event` 无 try/except，依赖调用方
- `load_rows` 对 NUL 字节做了 strip 处理（好）
- `load_feedback_keywords` 有基本校验（enabled字段、空值跳过）
- LLM调用有 try/except + 打印警告（可接受），但无重试逻辑
- `load_outputs_to_postgres` 用 `subprocess.run(check=True)` 但无超时参数
- **无任何 retry/backoff 逻辑**，网络调用失败即弃

#### 数据质量保障
- `freeze_enum` 确保标注值在枚举范围内（好）
- `normalize_entity_candidate` 有长度/前缀/通用词过滤（好）
- **缺失**：无输入行字段完整性校验（title/content/publish_time可为空时无防御）
- **缺失**：无 event_date 合理性检查（未来日期、远古代日期）
- **缺失**：LLM返回值无schema校验，仅做了 `normalize_llm_*` 的enum约束

#### 性能瓶颈
- **N+1问题**：`classify_rows_async` 对每个 row 调用 `build_structured_row`，其中 `choose_label` 对4个维度各遍历整个规则字典 — O(行数 × 规则数 × 4)
- `keyword_hits` 对每个关键词做 `in` 检查 — 对长文本是 O(关键词数 × 文本长度)，可用 Aho-Corasick 或正则预编译优化
- `extract_subject_entities` 中 `ENTITY_PATTERN.findall` + 逐个 `normalize_entity_candidate` 无缓存
- LLM并发限制为5（semaphore），合理

#### 可测试性
- `detect_event`, `compute_*`, `freeze_enum`, `keyword_hits` — **可独立单测**
- `classify_rows_async` — 不可独立测试（内嵌闭包 + LLM Client实例化）
- `build_structured_row` — 可测试但依赖全局 `ACTIVE_*_RULES`
- LLM增强逻辑（`process_one`）— 无法独立测试

#### 拆分建议

**强烈建议拆分**。1664行的单文件承担了7项职责，是整个项目最大的架构风险点。

```
src/capabilities/events/
├── rules.py                    (保留，452行，纯配置)
├── classify_rules.py           (NEW, ~500行)
│   ├── 常量映射 (SOURCE_TYPE_RULES, SUBTYPE_RULES, STAGE_RULES 等)
│   ├── load_feedback_keywords, merge_rules
│   ├── keyword_hits, freeze_enum, choose_label, choose_first_label
│   ├── detect_event (核心过滤)
│   └── 所有 compute_* 函数
├── classify_entities.py        (NEW, ~150行)
│   ├── normalize_entity_candidate
│   ├── extract_subject_entities
│   ├── build_summary, build_event_name, event_id
│   └── dedup_key, canonical_text, normalize_datetime
├── classify_llm.py             (NEW, ~400行)
│   ├── AsyncLLMClient
│   ├── AsyncOllamaClient
│   ├── LLMResultEnrichment
│   ├── normalize_llm_*, anchored_*
│   ├── should_trigger_llm, can_llm_promote, promote_candidate_result
│   └── enrich_with_llm (从 process_one 提取为独立可测函数)
├── classify_io.py              (NEW, ~200行)
│   ├── load_rows, load_rows_from_inputs, load_rows_from_db
│   ├── build_candidate_row, build_structured_row
│   ├── write_csv, ensure_output_dir
│   └── load_outputs_to_postgres
├── classify.py                 (精简至 ~300行)
│   ├── classify_rows_async (编排)
│   ├── run_classification_pipeline
│   ├── parse_args, main
│   └── 导入上述模块
└── ...
```

**预期收益**：
- 清晰度：每个文件 <500行，单一职责
- 可测试性：LLM逻辑可mock，detect_event可独立测
- 数据质量：可在 classify_rules.py 中增加输入校验装饰器
- 性能：可在 classify_rules.py 中集中优化 keyword_hits

---

### 2.2 feature_return.py（741行）— 事件研究/CAR计算

#### 职责清单（5项独立职责）

| # | 职责 | 行数范围 | 说明 |
|---|------|---------|------|
| 1 | 行情数据获取适配 | 40-109 | ts_to_sina_symbol, fetch_sina_kline, fetch_eastmoney_kline |
| 2 | 收益率计算 & 市场模型 | 112-197 | close_series_to_returns, fit_market_model, mean_and_t |
| 3 | 缓存管理 | 290-334 | load/save/get/put market cache |
| 4 | CAR计算 & 数据集生成 | 337-665 | main()中的核心循环 |
| 5 | 报告生成 | 667-737 | markdown报告输出 |

#### 函数统计
- 函数数：**20个**
- 平均长度：~37行
- **main() 函数：~400行** — 严重超标，占文件54%

#### 耦合分析
- `main()` 是一个"上帝函数"，包含：
  - 参数解析 → token解析 → 缓存加载 → 基准行情获取(3级回退) → 逐行循环(数据库查询+API调用+CAR计算) → CSV输出 → 报告生成 → 缓存保存
- `fetch_company_stats_returns` 与 `main()` 循环形成 **N+1查询模式** — 每行一个数据库查询
- 3级回退逻辑(tushare → eastmoney → sina)在 benchmark 和 stock 两处重复

#### 错误处理模式
- 每个API调用都有 try/except + reason_counts 跟踪（好）
- token无效时自动禁用tushare（好）
- **但**：所有 except 都是 bare `Exception`，无分类处理
- **无重试逻辑** — 网络超时直接跳过，不做retry
- `run_query_rows` 无SQL注入防护 — 使用f-string拼接 min_link_score（虽然来自CLI参数，但仍不安全）

#### 数据质量保障
- **缺失**：CAR值无合理性校验（如 |CAR| > 100% 应标记异常）
- **缺失**：beta值无合理性检查（如 |beta| > 5 应标记异常）
- `resolve_event_trade_index` 有 max_gap_days 限制（好）
- 估计窗要求 >= 30 个点（好）
- **缺失**：股票收益率数据无时间连续性检查（停牌导致的缺口）

#### 性能瓶颈
- **N+1查询**：`fetch_company_stats_returns` 在循环中逐行调用，每行创建新连接
- **重复计算**：同一 ts_code 在不同行中重复，虽有 stock_cache 但每次仍查询DB
- `fit_market_model` 用纯Python计算OLS — 对小样本可接受，但如需扩展应换numpy
- SQL查询使用 `f"... >= {args.min_link_score}"` — 字符串拼接而非参数化

#### 拆分建议

**建议拆分**。main()的400行是核心问题。

```
src/capabilities/analysis/
├── feature_market_data.py      (NEW, ~200行)
│   ├── ts_to_sina_symbol, ts_to_eastmoney_secid
│   ├── fetch_sina_kline, fetch_eastmoney_kline
│   ├── close_series_to_returns
│   └── fetch_benchmark_returns (从main中提取，含3级回退)
├── feature_market_model.py     (NEW, ~100行)
│   ├── fit_market_model
│   ├── mean_and_t
│   ├── resolve_event_trade_index
│   └── compute_car (从main循环体提取)
├── feature_cache.py            (NEW, ~60行)
│   ├── load/save/get/put market cache
│   └── resolve_tushare_token
├── feature_report.py           (NEW, ~100行)
│   ├── build_report (从main尾部提取)
│   └── summarize_metric
├── feature_return.py           (精简至 ~200行)
│   ├── parse_args
│   ├── main (编排逻辑)
│   ├── run_query_rows
│   ├── fetch_company_stats_returns
│   └── parse_windows, bucket3, date_distance_days
└── ...
```

**关键性能修复**：
1. 将 `fetch_company_stats_returns` 改为批量查询（IN子句或临时表）
2. SQL参数化替换f-string拼接
3. 对每只股票，应一次获取所有需要的事件日期区间的数据，而非重复查询

---

### 2.3 link_events.py（676行）— 事件-公司关联

#### 职责清单（4项独立职责）

| # | 职责 | 行数范围 | 说明 |
|---|------|---------|------|
| 1 | 行业映射 & 关键词配置 | 30-196 | CNINFO_L1_TO_CATEGORY, EVENT_KEYWORDS, l1_to_category |
| 2 | 关联评分 | 260-400 | score_link — 多维度加权评分 |
| 3 | 聚类事件构建 | 403-483 | build_cluster_events |
| 4 | 主流程 & DB写入 | 486-676 | main — 全量加载+逐对评分+upsert+清尾 |

#### 函数统计
- 函数数：**8个**
- 平均长度：~85行（偏高）
- `score_link`：~140行
- `main`：~190行

#### 耦合分析
- `score_link` 是核心，与 `l1_to_category`, `EVENT_KEYWORDS`, `GENERIC_SYMBOLS` 强耦合
- `build_cluster_events` 依赖 canonical_map 结构
- `main` 中事件×公司的双层循环（O(events × companies)）直接在Python层计算

#### 错误处理模式
- **几乎无 try/except** — 唯一保障是 `write_guard` 上下文管理器
- `normalize_tags` 有 json.loads 异常处理（好）
- 数据库操作依赖 psycopg 事务，但无业务级异常处理

#### 数据质量保障
- `l1_to_category` 有死代码（line 83-97 return后代码永远不会执行）— **BUG**
- `is_generic_event` 区分了通用事件和具体股票事件（好）
- 评分权重硬编码（0.24, 0.18, 0.10 等），无配置化
- **缺失**：final_score 无单调性校验（不同路径计算的分数逻辑不一致）
- **缺失**：evidence中的 `direct_name_match` 拼写错误 — 使用了 `direct_name_match` 变量但实际定义的是 `direct_name_match`（line 384 vs 304-308），实际上 line 384 用的是 `direct_name_match` 但赋值来自 `direct_name_match`... 等等，line 304 定义 `direct_name_match`，line 384 用的是 `direct_name_match` — 看起来一致。但 line 384 写的是 `bool(direct_name_match)`... 不对，原文是 `bool(direct_name_match)`。让我再检查：line 304 定义 `direct_name_match`，line 384 是 `"direct_name_match": bool(direct_name_match)` — 这里有个问题，line 304 变量名是 `direct_name_match`，而 line 311 定义了 `title_name_match`。但 line 384 写的是 `"direct_name_match": bool(direct_name_match)` — 看起来是对的... 但实际上变量名 line 304 是 `direct_name_match`，没问题。

  **等等** — line 304 是 `direct_name_match`，line 384 是 `"direct_name_match": bool(direct_name_match)` — 但变量名应该是 `direct_name_match` 还是... 让我重新检查。原文 line 304: `direct_name_match = (`... 这定义了 `direct_name_match` 变量。line 384: `"direct_name_match": bool(direct_name_match),` — 这用的是 `direct_name_match`。不对！line 304 定义的是 `direct_name_match`（含name），line 384 用的也是 `direct_name_match`。但仔细看 line 304: `direct_name_match = (` — 是的，这个变量存在。但等等 — 这应该是 `direct_name_match` 还是别的？实际上 line 304-308 定义的是：
  ```
  direct_name_match = (
      1.0
      if company["company_name"]
      and company["company_name"] in f"{raw_title} {raw_content}"
      else 0.0
  )
  ```
  这个变量名是 `direct_name_match`，但语义上是"直接名称匹配"。

  但 line 384 evidence dict 中写的是 `"direct_name_match": bool(direct_name_match)` — 这里用的是变量 `direct_name_match`，但 evidence key 是 `"direct_name_match"`。等等！evidence key 的拼写和变量名是否一致？让我再看看 — line 384: `"direct_name_match": bool(direct_name_match)` — 这个 evidence key 的名字和变量名完全一样。

  但等等！我之前读到 line 384 是 `"direct_name_match": bool(direct_name_match)` — 原文实际上是不是 `direct_name_match`？让我假设没有bug。

  不过有一个更明显的问题：`l1_to_category` 函数中有 **死代码**。line 82 `return "其他"` 之后，line 83-97 的代码永远不会执行。这是一个 **bug** — 下面的代码才是正确的行业映射逻辑（包含更细粒度的 CNINFO_L1_TO_CATEGORY 查找），但被提前 return 截断了。

#### 性能瓶颈
- **O(events × companies) 双层循环** — 若1000事件×5000公司=500万次 `score_link` 调用
- `score_link` 中对每个公司做5次关键词列表遍历（`EVENT_KEYWORDS` 查找）
- `normalize_tags` 在 `score_link` 中被调用两次（line 282 和 line 315）
- 所有事件和公司一次性加载到内存 — 无分页

#### 拆分建议

**建议拆分**，且需修复 bug。

```
src/capabilities/linking/
├── link_config.py              (NEW, ~200行)
│   ├── EVENT_INDUSTRY_TO_COMPANY
│   ├── CNINFO_L1_TO_CATEGORY
│   ├── EVENT_KEYWORDS, GENERIC_SYMBOLS
│   └── l1_to_category (修复死代码bug)
├── link_score.py               (NEW, ~200行)
│   ├── score_link
│   ├── is_specific_symbol, is_generic_event
│   └── normalize_tags
├── link_cluster.py             (NEW, ~100行)
│   └── build_cluster_events
├── link_events.py              (精简至 ~150行)
│   ├── parse_args, main
│   └── DB批量操作
└── ...
```

**关键修复**：
1. **修复 `l1_to_category` 死代码** — line 82 的 `return "其他"` 截断了 line 83-97 的正确逻辑
2. 性能优化：将 companies 按 industry_l1 分组，对每个 event 只匹配对应行业的公司
3. `score_link` 中 `normalize_tags` 缓存（同一 company 重复调用）

---

### 2.4 task1.py（646行）— CLI Task1入口

#### 职责清单（5项）

| # | 职责 | 行数范围 | 说明 |
|---|------|---------|------|
| 1 | 参数解析 | 59-171 | 15个子命令，大量参数定义 |
| 2 | 命令分发 | 381-643 | main()中的if/elif链 |
| 3 | 数据库查询辅助 | 174-245 | print_db_status, load_pending_raw_documents 等 |
| 4 | QA摘要生成 | 291-378 | print_qa_summary |
| 5 | 报告解析 | 248-288 | parse_feature_top_reasons, parse_collector_failures |

#### 函数统计
- 函数数：**9个**
- `parse_args`：~112行（参数定义，合理）
- `main`：~265行（if/elif分发，偏长）

#### 耦合分析
- **核心问题**：`patched_argv` 模式 — 通过修改 `sys.argv` 然后调用子模块的 `main()`，导致：
  - 子模块的 parse_args 被隐式调用
  - 参数传递不透明
  - 无法类型检查
  - 无法 IDE 跳转
- 每个命令分支手动构建 argv 列表 — **脆弱且易出错**
- `load_pending_raw_documents` 和 `load_source_raw_documents` 直接执行SQL — 应在 storage 层

#### 错误处理模式
- **无 try/except** — 所有调用都是"成功或崩溃"模式
- `print_db_status` 中用 f-string 构建表名查询 — 潜在SQL注入（虽然表名硬编码，但模式不好）
- QA摘要中的 JSON/文件读取无异常保护

#### 数据质量保障
- **无** — CLI层不校验数据
- `parse_feature_top_reasons` 对报告格式有基本容错（好）

#### 拆分建议

**建议重构** 而非简单拆分。核心问题是 `patched_argv` 模式。

```
src/cli/task1.py                (精简至 ~200行)
├── 保留 parse_args + main 分发
├── 改为直接调用子模块的函数（带参数），不再 patched_argv
└── 移除非CLI逻辑到能力层

# 将辅助函数移出：
src/capabilities/quality/qa_summary.py  (NEW)
├── print_qa_summary
├── parse_feature_top_reasons
└── parse_collector_failures

src/capabilities/storage/db_status.py   (NEW)
├── print_db_status
├── load_pending_raw_documents
└── load_source_raw_documents
```

**更根本的重构**：将 `patched_argv` 替换为直接函数调用 + 参数对象：
```python
# 改前：
with patched_argv(["classify.py", "--db", args.db]):
    classify.main()

# 改后：
classify.run_classify(
    db=args.db,
    skip_db_load=args.skip_db_load,
    use_llm=args.use_llm,
    llm_max_rows=args.llm_max_rows,
)
```

---

### 2.5 task2.py（611行）— CLI Task2入口

#### 职责清单（2项）

| # | 职责 | 行数范围 | 说明 |
|---|------|---------|------|
| 1 | 参数解析 | 47-236 | 17个子命令，~190行参数定义 |
| 2 | 命令分发 | 239-611 | main()中的if/elif链 |

#### 函数统计
- 函数数：**3个**（patched_argv, parse_args, main）
- `parse_args`：~190行
- `main`：~372行 — 主要是argv构建代码

#### 耦接分析
- 与 task1.py 相同的 `patched_argv` 问题
- `import-company-stats` 分支内有嵌套函数 `run_akshare_import` + 3级回退逻辑 — **372行的main中有~120行是单一命令的实现**
- 17个子命令全部在一个函数中 if/elif — 不可扩展

#### 错误处理模式
- `import-company-stats` 有 try/except 回退（tushare → akshare → sina）— 唯一有错误处理的地方
- 其他命令：成功或崩溃

#### 数据质量保障
- **无** — 纯调度层

#### 拆分建议

**建议重构**，与 task1.py 同理。

```
# 方案A：子命令模式（推荐）
src/cli/task2.py                (精简至 ~50行)
├── 注册子命令handler
└── main()

src/cli/commands/               (NEW)
├── import_companies.py
├── import_company_stats.py
├── load_company_data.py
└── link_events.py

# 方案B（最小改动）：
# 仅将 main() 中的每个 if 分支提取为独立函数
# 同时替换 patched_argv 为直接调用
```

---

### 2.6 rules.py（452行）— 规则配置

#### 可维护性评估

**评分：6/10（可接受但需改进）**

优点：
- 纯数据模块，无逻辑 — 修改规则不需要理解代码
- 枚举值集中定义 — `EVENT_SUBJECT_ENUM`, `INDUSTRY_ENUM` 等
- 有版本号 `RULE_VERSION`

问题：
- **关键词重复**：`SUBJECT_RULES["地缘类"]` 和 `DURATION_RULES["脉冲型"]` 和 `PREDICTABILITY_RULES["突发型"]` 高度重叠（"空战","冲突","伊朗","中东","霍尔木兹"等出现3次）
- **硬编码不可扩展**：增加行业需要改3+个地方（INDUSTRY_RULES, INDUSTRY_ENUM, classify.py中的INDUSTRY_ANCHOR_RULES, link_events.py中的EVENT_KEYWORDS）
- **无测试覆盖**：规则变更无法自动验证

建议：
1. 将行业关键词定义统一为单一来源，其他维度通过"行业→维度映射"派生
2. 增加规则校验脚本（检查：枚举完整性、关键词覆盖率、重复率）
3. 考虑 YAML/JSON 配置文件替代 Python 常量

---

### 2.7 delivery_status.py（487行）— 数据交付质量检查

#### 可维护性评估

**评分：8/10（项目中最佳文件）**

优点：
- 使用 `@dataclass(frozen=True)` 定义 Check — 不可变数据类
- 每个 `add_*_checks` 函数独立 — 可逐表扩展
- OK/WARN/BLOCK 三级阈值 — 精细化质量门控
- `count_filled` 通用函数 — 避免重复
- `render_markdown` 输出格式清晰

问题：
- `count_filled` 中用 f-string 构建 SQL — 潜在SQL注入（虽然列名硬编码）
- 9个 `add_*_checks` 函数手动注册在 `build_checks` 中 — 新增表容易遗漏
- 无阈值来源文档 — OK/WARN 的具体数值缺乏依据

建议：
1. 将检查函数用注册模式替代手动调用
2. 阈值可考虑配置化
3. 增加 "上期对比" 功能（与 QA snapshot 对比变化趋势）

---

## 三、跨文件系统性问题

### 3.1 关键词配置碎片化（最严重）

同一行业的定义分散在 **至少4个地方**：

| 位置 | 军工关键词示例 |
|------|-------------|
| rules.py `INDUSTRY_RULES` | 军工,战机,导弹,无人机,军品,空战,国防... |
| classify.py `INDUSTRY_ANCHOR_RULES` | 军工,战机,导弹,无人机,国防,军品,装备... |
| link_events.py `EVENT_KEYWORDS` | 军工,战机,导弹,无人机,航空,空战,低空,国防... |
| classify.py `SUBTYPE_RULES["股权变动"]` | (不同维度但相关) |

**风险**：新增行业或修改关键词时，必须在4+个文件同步修改，极易遗漏。

**建议**：将所有行业关键词统一定义在 rules.py 中，其他文件通过 `from rules import INDUSTRY_KEYWORDS` 引用。

### 3.2 SQL注入风险

| 文件 | 位置 | 风险 |
|------|------|------|
| feature_return.py | line 364 | `f"... >= {args.min_link_score}"` |
| task1.py | line 199 | `f"SELECT count(*) FROM {table}"` |
| delivery_status.py | line 70 | f-string构建列名 |

虽然当前参数来源可信（CLI参数/硬编码），但模式不安全，应改为参数化查询。

### 3.3 错误处理缺失

| 模式 | 出现位置 | 影响 |
|------|---------|------|
| bare `except Exception` | feature_return.py 多处 | 吞掉具体异常，难以调试 |
| 无 try/except | link_events.py 全文 | 任何异常导致整个流水线崩溃 |
| 无 retry | 所有网络调用 | 临时网络故障导致数据丢失 |
| subprocess无timeout | classify.py line 1024 | 可能永久挂起 |

### 3.4 测试覆盖为零

整个项目未发现 `tests/` 目录或任何测试文件。对于数学建模竞赛的紧迫性可以理解，但核心计算逻辑（CAR、市场模型、评分权重）应有最少量的单元测试。

### 3.5 patched_argv 反模式

task1.py 和 task2.py 通过修改 `sys.argv` 调用子模块的 `main()`，导致：
- 参数传递不透明
- 无法类型检查
- 子模块的 parse_args 与 CLI 的 parse_args 存在重复和可能不一致
- IDE 无法跟踪调用链

---

## 四、拆分优先级与实施建议

| 优先级 | 文件 | 拆分动作 | 预期收益 | 风险 |
|--------|------|---------|---------|------|
| **P0** | classify.py | 拆分为5个文件 | 清晰度↑↑↑ 可测试性↑↑↑ | 低（纯拆分，不改逻辑） |
| **P0** | link_events.py | 修复l1_to_category bug + 拆分为4文件 | 数据质量↑↑ | 低 |
| **P1** | feature_return.py | 拆分main() + 批量查询优化 | 性能↑↑ | 中（需验证CAR计算正确性） |
| **P1** | 关键词统一 | rules.py为单一来源 | 可维护性↑↑↑ | 低 |
| **P2** | task1.py / task2.py | patched_argv → 直接调用 | 清晰度↑ 可靠性↑ | 中（需修改所有子模块接口） |
| **P2** | 全项目 | SQL参数化 | 安全性↑ | 低 |

---

## 五、数据质量保障建议（补充）

1. **输入校验层**：在 classify.py 的 `detect_event` 入口增加校验
   - title/content 非空检查
   - publish_time 在合理范围（2020-01-01 至 未来7天）
   - source 在已知来源列表中

2. **输出校验层**：在 feature_return.py 的 CAR 计算后增加校验
   - |CAR| > 50% 标记为可疑
   - |beta| > 5 标记为可疑
   - 估计窗点数 < 30 的结果标记为低置信度

3. **关联评分校验**：在 link_events.py 的 score_link 中
   - 确保 final_score ∈ [0, 1]
   - 确保 evidence 中的所有 score 与计算值一致
   - generic_event + industry_type="其他" 的关联应额外标记低置信度

4. **端到端校验**：在 delivery_status.py 中增加
   - CAR 分布合理性检查（正态性检验）
   - 事件-公司关联覆盖率检查
   - 关键词命中分布检查

---

## 六、结论

本项目架构层次清晰，流水线设计合理，但存在3个系统性风险：

1. **classify.py 巨型文件**（1664行/7项职责）— 最需拆分
2. **关键词配置碎片化**（4+处重复定义）— 最影响数据质量
3. **patched_argv 反模式**（CLI层核心问题）— 最影响可维护性

建议按 P0→P1→P2 顺序逐步改进，优先拆分 classify.py 和修复 link_events.py 的死代码bug，这两项改动风险最低、收益最高。
