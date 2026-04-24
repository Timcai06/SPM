# 原始来源能力矩阵

> 目标：把 `raw_documents` 的扩量能力、正文质量能力、以及 2025/2026 的可执行动作讲清楚。  
> 本文只讨论 raw 层，不把事件分类结果当成采集前置条件。  
> 更新时间：`2026-04-23`

## 当前判断口径

### 1. raw 层决策口径

raw 层只看三件事：

1. `source-driven`：这个来源有没有稳定 collector / history 主链
2. `time-driven`：2025/2026 覆盖是不是太薄
3. `coverage-driven`：`content` 有没有正文、正文够不够长

### 2. 正文质量门槛

本文默认使用两层门槛：

- **合格正文**：`length(content) >= 80`，且 `content != title`
- **强正文**：`length(content) >= 300`，且 `content != title`

`collect-history` 现在已经支持直接按强正文门槛过滤。  
但对日常操作来说，不推荐继续手动拼这些参数。优先用：

```bash
./SPM ingest full DB=stock_event_mining
./SPM status raw DB=stock_event_mining
```

底层质量门槛和来源分流，会由系统内部处理。
这些来源级规则集中在：

- `src/modules/collectors/domain/source_profiles.py`

所以后面新增来源、调整页数、调整并发、调整附件 2 粗分类时，优先改 source profile，而不是改 `Makefile` 里的大段命令。

如果只是开发或调试，才需要直接用 `collect-history`：

```bash
python3 src/cli/collect.py collect-history \
  --source yicai-news \
  --start-date 2025-01-01 \
  --end-date 2026-04-23 \
  --quality-body-only \
  --min-content-length 300 \
  --skip-db-load
```

---

## 当前 2025/2026 来源家族快照

来自 `stock_event_mining.raw_documents`：

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

### 解释

- `巨潮资讯网` 仍然是绝对主源，但本轮不是我们的平衡基准。
- `中国政府网 / 中国证监会 / 国家发改委 / 东方财富` 已经在库里证明了自己能稳定产出强正文。
- `第一财经 / 工信部` 的**新解析器**已经在抽样里证明能产出强正文，但还没有被大规模回写到主库里，所以当前 DB 统计还没追上。
- `36氪 / 财新 / 上交所 / 深交所` 目前更适合先补覆盖，不适合按正文型目标去冲。

---

## 现有来源是否已进入 `collect-history` 主链

| history source | 已进主链 | 当前状态 |
|---|---|---|
| `cninfo-disclosure` | 是 | 历史公告主源，可做全文回填 |
| `akshare-news` | 是 | 聚合新闻源，量足但正文门槛一般 |
| `gov-news` | 是 | 正文质量强 |
| `ndrc-policy` | 是 | 正文质量强，但总量有限 |
| `csrc-policy` | 是 | 正文质量强 |
| `miit-policy` | 是 | 已切到搜索 API，抽样可出强正文 |
| `sse-announcements` | 是 | 公司行为类，正文偏摘要 |
| `szse-announcements` | 是 | 公司行为类，正文偏摘要 |
| `szse-suspension` | 是 | 事实型源，不是正文型源 |
| `eastmoney-industry` | 是 | 正文质量强 |
| `kr36-flash` | 是 | 有内容，但大多低于强正文门槛 |
| `caixin-mini` | 是 | 有内容，但强正文命中率偏低 |
| `yicai-news` | 是 | 已修正文抽取，抽样强正文命中高 |

---

## 抽样验证结果

下面这些结果来自 `--skip-db-load --quality-body-only --min-content-length 300` 的抽样验证：

| history source | 抽样参数 | 通过条数 | 结论 |
|---|---|---:|---|
| `miit-policy` | `pages=2 size=10` | `15` | 已通过强正文门槛 |
| `yicai-news` | `pages=2 size=10` | `16` | 已通过强正文门槛 |
| `caixin-mini` | `pages=2 size=10` | `1` | 质量不稳定，不适合直接冲量 |
| `kr36-flash` | `pages=2 size=10` | `0` | 当前不适合按强正文门槛冲量 |

### 当前 raw 层质量分组

这部分是系统内部策略依据，不要求日常操作记忆。

#### A. 已通过强正文门槛，适合继续扩量

- `gov-news`
- `ndrc-policy`
- `csrc-policy`
- `miit-policy`（抽样验证）
- `eastmoney-industry`
- `yicai-news`（抽样验证）

#### B. 已接入主链，但不适合按强正文目标冲量

- `kr36-flash`
- `caixin-mini`
- `sse-announcements`
- `szse-announcements`
- `szse-suspension`
- `akshare-news`

---

## 与附件 2 的四类事件粗分类对齐

`raw_documents.symbol_or_subject` 现在应该统一理解成附件 2 的**事件粗粒度分类**：

- `政策类事件`
- `公司行为事件`
- `行业/技术事件`
- `宏观/地缘事件`

`./SPM ingest full DB=stock_event_mining` 会在补来源、补正文、巨潮回填之后，自动把这个字段按 `source` 规范化到这 4 类。这个步骤只更新 `symbol_or_subject`，不改正文、不改 URL、不改发布时间。

当前 2025/2026 已落到这 4 类的行数（只统计这 4 类值）：

| 粗分类 | 行数 |
|---|---:|
| 公司行为事件 | 3,369 |
| 宏观/地缘事件 | 838 |
| 政策类事件 | 718 |
| 行业/技术事件 | 324 |

说明：

- 新写入数据会从采集端直接写入附件 2 四类。
- 历史数据由 `ingest full` 末尾的规范化步骤兜底，避免旧的股票代码、来源侧短标签继续占用这个字段。

---

## 2025/2026 的直接动作

### 1. 继续扩量的来源

优先级最高：

1. `yicai-news`
2. `eastmoney-industry`
3. `csrc-policy`
4. `gov-news`
5. `ndrc-policy`
6. `miit-policy`

### 2. 当前以覆盖优先方式补数据的来源

- `kr36-flash`
- `caixin-mini`
- `sse-announcements`
- `szse-announcements`
- `szse-suspension`

这些来源可以保留在 raw 层，但不应该和正文型来源混成同一套补数据策略。

### 3. 当前最现实的全量补数据目标

要很诚实地说：

- `yicai-news`、`eastmoney-industry` 有希望继续把正文型数据做厚
- `gov-news / ndrc-policy / csrc-policy / miit-policy` 更像**高质量政策源**，但 2025/2026 的自然供给量有限

所以后面的命令应该区分：

1. **正文优先型来源**
2. **自然上限型来源**
