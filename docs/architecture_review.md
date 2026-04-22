# 架构审查（当前状态）

## 总体判断

项目已经从“赛题脚本”转向“事件驱动量化研究平台”，当前主结构是：

- `cli/`：领域命令入口
- `pipelines/`：少量多步编排
- `modules/*/jobs`：任务入口
- `modules/*/services`：业务编排
- `modules/*/adapters`：外部系统与 DB 边界
- `modules/*/domain`：纯规则与纯计算
- `capabilities/*`：仍在逐步退出的 legacy 实现

## 当前优点

1. **入口层语义已经明确**
   - 入口按 `collect / events / linking / graph / research / quality` 拆分。
   - 旧的 `task1/2/3` 已经退出公共命令面。

2. **CLI 到 job 的参数流已收口**
   - 主链不再依赖 `patched_argv` 注入。
   - `main(argv)` / `parse_args(argv)` 已经成为标准模式。

3. **主链模块边界清晰**
   - collectors、events、companies、linking、graph、analysis、quality 的职责已经可见。

## 当前问题

1. **legacy 仍未完全退出**
   - `capabilities.analysis`、`capabilities.storage` 仍有桥接存在。
   - 现在的问题不在 CLI，而在更深层 service/adapter 之下。

2. **研究数据治理还不够**
   - 缺统一的 run metadata / batch provenance。
   - 研究、回填和标签生成还不够可追溯。

3. **市场与基本面库偏薄**
   - 这已经成为量化研究有效性的主要瓶颈，而不是入口层代码质量。

## 近期优化方向

1. 继续做 `raw_documents` 正文化
2. 补足 point-in-time 市场与基本面数据
3. 建 run metadata / dataset lineage
4. 补全真实链路 smoke test
5. 再逐步压缩 `capabilities/*` 的桥接范围
