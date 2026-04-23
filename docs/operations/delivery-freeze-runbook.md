# 交付冻结运行手册

本说明用于明天交付前的冻结期。目标只有两个：

1. 保证当前跑批结果可解释、可复核。
2. 禁止任何会改变现有交付语义的高风险改动。

## 冻结原则

交付前禁止：

- 删除 `2023/2024` 历史数据。
- 再次大改采集器接口逻辑。
- 修改 `structured_events` 分类规则和 taxonomy。
- 修改正在运行的回填/采集作业参数模型。

交付前允许：

- 只读 SQL 检查。
- 导出命令整理。
- 运行说明与质量说明补充。
- 不影响现有进程的低风险工程整理，例如文档修正、测试补充、代码边界收口。

## 当前主链定义

- `collect-history`：发现新数据，按 source/symbol/date 拉取原始记录。
- `backfill-cninfo-fulltext`：基于已有 `raw_documents.url` 回填巨潮正文。
- `classify` / `classify-pending` / `reclassify-source`：把 `raw_documents` 转成 `structured_events`。
- `linking/graph`：基于结构化事件继续构建 `event_company_links` 与传播关系。

## 交付口径

### 原始文本

- 正文型原始文本：`content` 长度 >= 300，且不是标题复写。
- 强正文：`content` 长度 >= 800，且不是标题复写。
- 标题型原始文本：`content` 为空、等于 `title`、等于去掉公司名前缀后的标题，或长度 < 300。

### 结构化事件

交付前只检查：

- `unrefined_pct`
- `empty_entities_pct`
- `sw_fill_pct`
- `shock_filled`
- `chain_stage_rows`

不在冻结期改动分类规则去追求更好数字。

## 只读检查命令

### 运行进程

```bash
pgrep -f "collect.py collect-history|collect.py backfill-cninfo-fulltext" | wc -l
```

### 2025 巨潮正文合格率

```bash
/opt/homebrew/bin/psql -d stock_event_mining -c "
with base as (
  select
    count(*) as total_rows,
    count(*) filter (
      where length(coalesce(content,'')) >= 300
        and btrim(coalesce(content,'')) <> btrim(title)
        and btrim(coalesce(content,'')) <> btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
    ) as qualified_rows,
    count(*) filter (
      where length(coalesce(content,'')) >= 800
        and btrim(coalesce(content,'')) <> btrim(title)
        and btrim(coalesce(content,'')) <> btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
    ) as strong_rows
  from raw_documents
  where source='巨潮资讯网/历史公告'
    and publish_time >= timestamp '2025-01-01'
    and publish_time < timestamp '2026-01-01'
)
select * from base;
"
```

### 2025 结构化事件主质量

```bash
/opt/homebrew/bin/psql -d stock_event_mining -c "
select
  count(*) as events,
  count(*) filter (where event_subject_subtype='未细分') as unrefined_subtype,
  round(100.0 * count(*) filter (where event_subject_subtype='未细分') / nullif(count(*),0), 2) as unrefined_pct,
  count(*) filter (where subject_entities='[]'::jsonb) as empty_entities,
  round(100.0 * count(*) filter (where subject_entities='[]'::jsonb) / nullif(count(*),0), 2) as empty_entities_pct,
  count(*) filter (where sw_l1_industry <> '其他') as sw_filled,
  round(100.0 * count(*) filter (where sw_l1_industry <> '其他') / nullif(count(*),0), 2) as sw_fill_pct,
  count(*) filter (where chain_stage_count > 0) as chain_stage_rows,
  count(*) filter (where shock_source_type <> '其他') as shock_filled
from structured_events
where event_date >= date '2025-01-01'
  and event_date < date '2026-01-01';
"
```

## 导出规则

### 导出 2025 合格巨潮正文

```bash
mkdir -p '/Users/tim/Desktop/事件csv' && \
/opt/homebrew/bin/psql -d stock_event_mining -c "\copy (
  with base as (
    select
      *,
      regexp_replace(title, '^[^：:]+[：:]', '') as title_core,
      length(coalesce(content, '')) as content_len
    from raw_documents
    where source='巨潮资讯网/历史公告'
      and publish_time >= timestamp '2025-01-01'
      and publish_time < timestamp '2026-01-01'
  )
  select *
  from base
  where content_len >= 300
    and btrim(coalesce(content,'')) <> btrim(title)
    and btrim(coalesce(content,'')) <> btrim(title_core)
  order by publish_time desc, id desc
) to '/Users/tim/Desktop/事件csv/2025合格正文原始数据.csv' csv header"
```

## 交付说明模板

交付说明里至少要明确：

- 2025/2026 哪些 source 已经是正文型。
- 2023/2024 仍以标题型历史数据为主。
- `structured_events` 已可用，但高价值特征仍弱于主体稳定性。
- 当前最高优先级后续工作是 2025 巨潮正文回填，不是继续扩标题量。
