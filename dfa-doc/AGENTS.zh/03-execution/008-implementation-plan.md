# 执行计划与验证流程

## 当前运行态势

- Confirm current project phase and the next safe scope of work before making broad edits.

## 顶层护栏与核心规则 (首读必看)

- 第一原则： 验证关卡： workflow changes are not complete until `python3 src/cli/task1.py check` pass.
- 第二原则： 验证顺序： 1) `python3 src/cli/task1.py check`; stop at the first failing command before running later checks.
- 第三原则： 失败排查优先级： 1) rerun the first failing gate (`python3 src/cli/task1.py check`) to isolate command scope; 2) if failures persist, roll back generated docs to last known-good state and rerun `docagent refresh`.

## 即时关注事项

- Validate setup, run, and verify commands before broad edits.
- Refresh AGENTS docs after changing repository structure or workflow commands.
- Resolve the open repository-shape questions before taking on large refactors.

## 环境设置 (Setup)

```bash
Review README setup steps and install dependencies with the repository's package manager.
```

## 运行 (Run)

```bash
Run the primary local command from README examples (app start, CLI invocation, or generator refresh).
```

## 验证 (Verify)

```bash
Run repository verification commands from README or CI (lint/test/build equivalents).
```

## 辅助参考文档提炼 (Execution)

### 已确认的基准主张

- 验证关卡： workflow changes are not complete until `python3 src/cli/task1.py check` pass.
- 验证顺序： 1) `python3 src/cli/task1.py check`; stop at the first failing command before running later checks.
- 失败排查优先级： 1) rerun the first failing gate (`python3 src/cli/task1.py check`) to isolate command scope; 2) if failures persist, roll back generated docs to last known-good state and rerun `docagent refresh`.
- Run `python3 src/cli/task1.py check` 

### 待清理的矛盾点

- 未从支持文档中检测到直接的执行冲突。

### 悬而未决的问题

- 未从支持文档中检测到未决的执行事项。

## 执行层辅助参考文档

- `README.md`
