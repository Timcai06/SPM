# 工程整改 Backlog

本清单以“事件驱动量化研究平台”为目标，而不是赛题交付。

## P0

1. **正文资产继续做实**
   - 目标：`raw_documents` 尽可能从标题库转成可挖掘正文库。
   - 原则：优先回填已有 URL，不用标题量增长替代正文质量增长。

2. **点时研究数据补齐**
   - 补足市场、估值、换手、停牌、指数与行业环境字段。
   - 把 `security_features_daily` / `security_forward_labels_daily` / `market_environment_daily` 做成真正可研究的基础面板。

3. **run provenance 治理**
   - 建最小 `run metadata / batch lineage` 结构。
   - 让回填、分类、研究标签都能追溯到一次具体运行。

4. **真实链路 smoke test**
   - 覆盖 `collect -> events -> linking -> graph -> research -> quality` 的小批量链路。

## P1

1. **继续消化 legacy bridge**
   - 让 `modules/.../jobs|services|adapters` 成为主路径。
   - `capabilities/...` 只保留过渡实现，不再继续扩张。

2. **研究命名与输出统一**
   - 去掉用户可见的 `task1_* / task2_* / task3_*` 输出名。
   - 统一成领域语义的 dataset/report 名称。

3. **公共市场数据工具统一**
   - 保持 `fetch_sina_kline`、收益率转换和缓存逻辑单一实现。
   - 避免 analysis / storage 出现行为漂移。

4. **schema 迁移治理**
   - 从“大 SQL 文件 + ALTER IF NOT EXISTS”转向显式迁移记录。

## P2

1. **taxonomy 精修**
   - 继续拆细公司类二级分类，减少大桶标签。

2. **批量写库优化**
   - 评估 `COPY`、临时表合并和批量 update/upsert。

3. **研究层与回测层补齐**
   - 设计更适合量化研究的样本表、标签表和回测结果表。
