# 架构兼容性与规则

## 顶层护栏与核心规则 (首读必看)

- 第一原则： Resolve source-of-truth conflicts before changing CLI, adapter, or build-path behavior.
- 第二原则： Treat platform adapters as distribution details; keep contract changes centralized at CLI entry.

## 仓库类型判定信号

- 未从代码仓库结构中检测到额外的衍生产品信号。

## 事实来源 (Source of Truth)

- `README.md` for stated project goals, setup expectations, and user-facing examples

## 辅助参考文档提炼 (Architecture)

### 已确认的基准主张

- 任务 1 统一命令入口：src/cli/task1.py 
- 任务 2 统一命令入口：src/cli/task2.py 

### 待清理的矛盾点

- 未从支持文档中检测到直接的架构冲突。

### 悬而未决的问题

- 未从支持文档中检测到未决的架构事项。

## 核心参考历史文档

- `README.md`

## 兼容性边界规则

- 优先先改源码和配置，再刷新 `dfa-doc/AGENTS/` 文档。
- 不要让生成文档偏离仓库真实的入口点和工作流。

## 冲突项监控

- 未自动检测到重大冲突信号。
