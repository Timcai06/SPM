# 工程整改 Backlog

本清单按优先级划分为 `P0 / P1 / P2`，目标是把项目从“能跑”推进到“可信”。

## P0

1. **正文资产优先**
   - 目标：`raw_documents` 从标题库转成可挖掘正文库。
   - 原则：优先回填已有 URL，不再用标题量增长替代正文质量增长。

2. **交付文档与代码结构对齐**
   - README、运行说明、导出说明必须指向当前 `src/modules/...` 路径。
   - 不再保留误导性的旧 `capabilities/...` 主路径描述。

3. **停止新增 wrapper job 调 legacy module**
   - 新功能只进 `modules/`。
   - 旧 `capabilities` 只保留过渡逻辑，不再继续扩张。

4. **建立最小测试保护网**
   - CNInfo fixture/fallback
   - 分类 golden set
   - raw_documents 写库 contract test

## P1

1. **拆薄 `task1.py`**
   - 子命令注册与执行分离
   - 减少 `patched_argv` 形式桥接
   - 新命令优先走显式 service API

2. **collector 服务收口**
   - 采集 / 正文抽取 / 增量入库 / CSV 输出分层
   - 高频 DB 写入统一走 repository 边界

3. **收口 `analysis`**
   - 先把主链入口与旧 `capabilities.analysis` 解耦
   - 再逐步拆掉超大 legacy 文件

4. **收口 storage 写库边界**
   - `raw_documents` / `structured_events` / linking 的常用写库入口统一进入 `modules/.../adapters`

## P2

1. **schema 迁移治理**
   - 从“大 SQL 文件 + ALTER IF NOT EXISTS”转向显式迁移记录

2. **taxonomy 精修**
   - 重点拆细公司类二级分类，避免 `股权变动` 吞并过多事件

3. **批量写库优化**
   - 评估 `COPY`、临时表合并、批量 update/upsert 的性能改造

4. **analysis / rag / storage 深拆**
   - 在主链稳定后继续清理剩余 legacy 结构
