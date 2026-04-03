# 工作流

## 核心规则（首读）

- 第一原则： 验证关卡： workflow changes are not complete until `python3 src/cli/task1.py check` pass.
- 第二原则： 验证顺序： 1) `python3 src/cli/task1.py check`; stop at the first failing command before running later checks.
- 第三原则： 失败排查优先级： 1) rerun the first failing gate (`python3 src/cli/task1.py check`) to isolate command scope; 2) if failures persist, roll back generated docs to last known-good state and rerun `docagent refresh`.

## 文档契约

- 本页是该领域面向维护者的真相源；在 dual 模式下保持与 `dfa-doc/AGENTS/` 同步，并以 `dfa-doc/handbook.zh/` 作为人类视图根目录。
- 在行为变更的同一 PR 中更新本页；避免在没有命令或契约变化时做纯叙述式刷新。
- 在将本页标记为完成前，确保 setup/run/verify/triage 顺序可在干净 checkout 中执行。

## 双视图同步检查清单

- 编辑后用 dual 模式刷新，并确认 `dfa-doc/AGENTS/` 与 `dfa-doc/handbook.zh/` 在同一组变更中一起更新。
- 如果只更新了一侧，将其视为文档漂移，并在合并前解决。
- 刷新后运行文档中记录的 verify 命令，并保持两套文档系统中的故障排查顺序一致。

## 成对刷新规则

- 刷新契约： 一次 refresh/generate 应同时更新成对视图；不要单独修补某个 locale 或 audience。
- 路径契约：当行为变更影响共享真相源时，验证变更文件同时包含 `dfa-doc/AGENTS*/` 与 `dfa-doc/handbook*/` 的对应项。
- Quad 模式契约：当使用 `--output-mode quad` 时，在同一轮审查中验证全部四个根目录（`dfa-doc/AGENTS/`、`dfa-doc/AGENTS.zh/`、`dfa-doc/handbook/`、`dfa-doc/handbook.zh/`）。
- 执行配对规则：如果 `dfa-doc/handbook.zh/workflows.md` 因命令或顺序更新而修改，同时刷新两个 AGENTS 根下对应的执行路径。

## 双视图配对契约（规则）

- 结对模式规则：在 `dual` 模式下，人和机器的文档同源生成，必须作为一个完整的变更集进行评审。
- 语言输出规则：人类视图语言 `zh` 映射至目录 `dfa-doc/handbook.zh/`。
- 模板规则：人类视图模板变体 `paired-core` 是结对契约的一部分，在配对文档间必须保持一致。
- 路径对齐规则：`dfa-doc/handbook.zh/workflows.md` 与 `dfa-doc/AGENTS/03-execution/008-implementation-plan.md` 结对，用于 安装、验证与排障顺序。

## 配对的 Agent 文档（Dual 模式）

- `dfa-doc/AGENTS/03-execution/008-implementation-plan.md` 安装、验证与排障顺序.

## 输出边界（Human vs Agent）

- 使用 `dfa-doc/handbook.zh/` 记录面向维护者的政策与决策；使用 `dfa-doc/AGENTS/` 记录执行顺序、命令接线和交接运行手册。
- 如果一项变更影响两类读者，请在一次 dual refresh 周期中同时更新两套系统，而不是只修补一侧。
- 将维护者运行手册上下文保留在 `dfa-doc/handbook.zh/workflows.md` 中；将面向 agent 的步骤化执行计划保留在 `dfa-doc/AGENTS/workflows.md`（或分层执行文档）中。

## 双视图设计理由

- `dfa-doc/handbook.zh/` 与 `dfa-doc/AGENTS/` 是基于同一份仓库分析和事实锚点生成的两套视图。
- 当两套视图出现分歧时，将其视为 refresh 漂移，而不是独立的文档权威。
- 维护者运行手册上下文位于 `dfa-doc/handbook.zh/workflows.md` 中，而智能体动作的步骤顺序位于配对的 `dfa-doc/AGENTS/` 执行文档中。

## 安装

```bash
Review README setup steps and install dependencies with the repository's package manager.
```

## 运行

```bash
运行 README 示例中的主本地命令。
```

## 验证

```bash
Run verification commands from CI or README (lint/test/build equivalents).
```

## 综合摘要

- 已分析信源数量：`1`
- 成功提炼结论：`4` 条确认，`0` 条冲突，`0` 条未决

## 知识状态

### 已确认规则

- 验证关卡： workflow changes are not complete until `python3 src/cli/task1.py check` pass.
- 验证顺序： 1) `python3 src/cli/task1.py check`; stop at the first failing command before running later checks.
- 失败排查优先级： 1) rerun the first failing gate (`python3 src/cli/task1.py check`) to isolate command scope; 2) if failures persist, roll back generated docs to last known-good state and rerun `docagent refresh`.
- Run `python3 src/cli/task1.py check`

### 辅助信号

- 主要命令工作流围绕 `npm` package scripts 与仓库本地 verify 命令展开。

### 决策待办

- 未从支持文档中综合出未决的执行事项。

### 冲突观察清单

- 未从支持文档中综合出直接的执行冲突。

## 运行说明

- 保持本文件中的命令示例与 CI 和 README 指令一致。

## 更新触发条件

- 当 setup/run/verify 命令变化时，立即更新此运行手册。
- 当 CI 检查或发布门禁变化时，同步更新 Verify 和运行说明部分。

## 维护流程

- 为此文档指定一名维护负责人，并在行为变更的同一 PR 中更新它。
- 每个 Sprint 或每次发版前至少审阅一次此文档。
- 在 setup/run/verify 命令或 CI 工作流变更后更新。
- 未检测到重大综合冲突；重点是在实现变化后保持本页最新。

## 冷启动待办（文档较薄时）

- 已找到支持文档；继续将它们整合进本页，并归档过时重复项。

## 溯源

- `README.md`
