# 架构设计与技术决策

## 事实来源 (Source of Truth)

- `README.md` for stated project goals, setup expectations, and user-facing examples

## 顶层护栏与核心规则 (首读必看)

- 第一原则： Resolve source-of-truth conflicts before changing CLI, adapter, or build-path behavior.
- 第二原则： Treat platform adapters as distribution details; keep contract changes centralized at CLI entry.

## 文档与维护契约

- 本页是该领域面向维护者的真相源；在 dual 模式下保持与 `dfa-doc/AGENTS/` 同步，并以 `dfa-doc/handbook.zh/` 作为人类视图根目录。
- 在行为变更的同一 PR 中更新本页；避免在没有命令或契约变化时做纯叙述式刷新。
- 在修改 CLI、adapter 或构建路径行为前，先解决 source-of-truth 冲突。

## 双重视图同步清单

- 编辑后用 dual 模式刷新，并确认 `dfa-doc/AGENTS/` 与 `dfa-doc/handbook.zh/` 在同一组变更中一起更新。
- 如果只更新了一侧，将其视为文档漂移，并在合并前解决。
- 当 source-of-truth 文件移动时，先更新两套文档系统中的引用，再调整 adapter/构建路径规则。

## 结对刷新规则

- 刷新契约： 一次 refresh/generate 应同时更新成对视图；不要单独修补某个 locale 或 audience。
- 路径契约：当行为变更影响共享真相源时，验证变更文件同时包含 `dfa-doc/AGENTS*/` 与 `dfa-doc/handbook*/` 的对应项。
- Quad 模式契约：当使用 `--output-mode quad` 时，在同一轮审查中验证全部四个根目录（`dfa-doc/AGENTS/`、`dfa-doc/AGENTS.zh/`、`dfa-doc/handbook/`、`dfa-doc/handbook.zh/`）。
- 架构配对规则：如果 `dfa-doc/handbook.zh/architecture.md` 因边界或事实来源更新而修改，同时刷新两个 AGENTS 根下对应的架构路径。

## 双视图关联契约 (Rules)

- 结对模式规则：在 `dual` 模式下，人和机器的文档同源生成，必须作为一个完整的变更集进行评审。
- 语言输出规则：人类视图语言 `zh` 映射至目录 `dfa-doc/handbook.zh/`。
- 模板规则：人类视图模板变体 `paired-core` 是结对契约的一部分，在配对文档间必须保持一致。
- 路径对齐规则：`dfa-doc/handbook.zh/architecture.md` 与 `dfa-doc/AGENTS/02-architecture/004-tech-stack.md` 结对，用于 栈事实与平台锚点。
- 路径对齐规则：`dfa-doc/handbook.zh/architecture.md` 与 `dfa-doc/AGENTS/02-architecture/007-architecture-compatibility.md` 结对，用于 source-of-truth 与兼容性规则。

## 结对智能体文档 (双重模式)

- `dfa-doc/AGENTS/02-architecture/004-tech-stack.md` 栈事实与平台锚点.
- `dfa-doc/AGENTS/02-architecture/007-architecture-compatibility.md` source-of-truth 与兼容性规则.

## 文档输出边界 (人类与智能体)

- 使用 `dfa-doc/handbook.zh/` 记录面向维护者的政策与决策；使用 `dfa-doc/AGENTS/` 记录执行顺序、命令编排和运行手册。
- 如果一项变更同时影响两类受众，应在同一个同步周期内更新两套系统，而非仅单独修补一侧。
- 在 `dfa-doc/handbook.zh/architecture.md` 中保留架构理由；在 `dfa-doc/AGENTS/architecture.md`（或分层架构文档）中保留命令行、构建和事实来源护栏。

## 双视图设计逻辑

- `dfa-doc/handbook.zh/` 与 `dfa-doc/AGENTS/` 是基于同一份仓库分析和事实锚点生成的两套视图。
- 当两套视图出现分歧时，应将其视为“同步漂移”，而非独立的文档权威。
- 架构理由记录在 `dfa-doc/handbook.zh/architecture.md` 中，而面向智能体的操作边界保留在配对的 `dfa-doc/AGENTS/` 架构文档中。

## 检测到的技术信号

- 未从代码仓库结构中检测到额外的衍生产品信号。

## 系统版图映射

- 未自动检测到系统版图细节。

## 提炼总结

- 已分析信源数量：`1`
- 成功提炼结论：`2` 条确认，`0` 条冲突，`0` 条未决

## 知识健康度

### 已确认的基准主张

- 任务 1 统一命令入口：src/cli/task1.py
- 任务 2 统一命令入口：src/cli/task2.py

### 辅助参考信号

- 未从代码仓库结构中检测到额外的衍生产品信号。

### 决策后台 (未决事项)

- 未从支持文档中检测到未决的架构事项。

### 冲突监控清单

- 未从支持文档中检测到直接的架构冲突。

## 稳定性边界

- 当支持文档存在分歧时，以 source-of-truth 文件为准。
- Refresh both `dfa-doc/handbook.zh/` and `dfa-doc/AGENTS/` after architecture-impacting changes.

## 文档刷新触发条件

- 当 source-of-truth 文件、服务边界或运行时依赖变化时，更新本页。
- 当集成契约（routes/endpoints/storage）变化时，在同一 PR 中刷新架构说明。

## 文档日常维护流

- 为此文档指定一名维护负责人，并在行为变更的同一 PR 中更新它。
- 每个 Sprint 或每次发版前至少审阅一次此文档。
- 在边界、依赖或接口契约变更后更新。
- 未检测到重大综合冲突；重点是在实现变化后保持本页最新。

## 冷启动阶段待办 (文档薄弱时)

- 已找到支持文档；继续将它们整合进本页，并归档过时重复项。

## 溯源证明 (依据文件)

- `README.md`
