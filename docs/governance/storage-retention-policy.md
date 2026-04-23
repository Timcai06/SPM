# 存储保留与空间治理策略

这份文档只回答两件事：

1. 现在哪些表最占空间
2. 哪些表/数据可以重建，哪些不应该轻易删

## 当前空间热点

按当前 `stock_event_mining` 的库内占用，大头是：

| 表名 | 体量 |
|---|---:|
| `raw_documents` | 2565 MB |
| `event_candidates` | 983 MB |
| `structured_events` | 626 MB |
| `stg_event_candidates` | 625 MB |
| `stg_structured_events` | 351 MB |
| `event_company_links` | 230 MB |

结论很直接：

- **第一大头是 `raw_documents`**
- **第二大头是 stage 表**

## 分层保留原则

### 1. 长期保留：事实层和研究层

这些表默认应长期保留：

- `raw_documents`
- `event_candidates`
- `structured_events`
- `event_company_links`
- `event_propagation_edges`
- `security_features_daily`
- `security_forward_labels_daily`
- `event_research_samples`
- `control_research_samples`

原因：

- 它们是事实或研究结果层
- 它们支撑回溯、复核、建模和分析

### 2. 可重建：staging 层

这些表不应被当作长期资产：

- `stg_event_candidates`
- `stg_structured_events`

原因：

- 它们是装载缓冲
- 内容可由上游重新生成
- 不应长期占大空间

## 对 stage 表的建议

### 建议策略

默认采用：

- **平时保留**
- **每次重大跑批结束后清空**

推荐操作：

```sql
TRUNCATE TABLE stg_event_candidates RESTART IDENTITY CASCADE;
TRUNCATE TABLE stg_structured_events RESTART IDENTITY CASCADE;
```

或直接走项目入口：

```bash
./SPM status storage DB=stock_event_mining
./SPM status clean-stage DB=stock_event_mining --yes
make db-stage-clean DB=stock_event_mining YES=1
```

### 什么时候不要清

如果你还在：

- 排查当前一轮分类问题
- 对比 stage 和 final 差异
- 验证 pipeline 行为

那先别清。

### 什么时候该清

如果你已经：

- 完成当前一轮入库
- 没有依赖 stage 做调试
- 需要腾空间

那 stage 表是最先该清的对象。

## 对 `raw_documents` 的建议

### 当前现实

`raw_documents` 绝大多数来自：

- `巨潮资讯网/历史公告`

占比和体量都远高于其他来源。

按年份看：

| 年份 | 行数 | 合格正文率 |
|---|---:|---:|
| 2023 | 532352 | 0.00% |
| 2024 | 525197 | 0.00% |
| 2025 | 480115 | 39.26% |
| 2026 | 39976 | 29.00% |

### 保留策略建议

#### 2025 / 2026

建议保留。

原因：

- 已经有显著正文价值
- 是当前研究主战场

#### 2023 / 2024

不要立刻删。

当前更合理的做法是：

1. **先冻结**
2. **不再继续扩这两年的量**
3. 未来如果明确不用，再按年份做归档或删除

原因：

- 它们虽然正文质量差
- 但仍然是事实记录
- 一旦删除，会级联影响下游表

## 归档优先级

如果以后必须瘦身，建议按这个顺序：

1. 清空 `stg_event_candidates`
2. 清空 `stg_structured_events`
3. 清理历史 `output/` 跑批产物
4. 评估 `2023/2024 raw_documents` 是否归档到外部文件
5. 最后才考虑正式删除历史年份事实表内容

## 删除前必须确认的事

如果未来要删 `raw_documents` 的历史年份，必须先确认：

1. 是否还要用这些年份做回溯研究
2. 是否已有外部归档
3. 是否接受下游级联删除
4. 是否保留过样本或指标快照

## 一句话

当前最合理的空间治理，不是先删 `raw_documents`，而是：

1. **先清理 stage 表**
2. **保留 2025/2026**
3. **冻结 2023/2024，暂不扩、不急删**
