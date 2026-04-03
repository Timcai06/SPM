# Architecture Compatibility

## Top Rules (Read First)

- Rule 1: Resolve source-of-truth conflicts before changing CLI, adapter, or build-path behavior.
- Rule 2: Treat platform adapters as distribution details; keep contract changes centralized at CLI entry.

## Repo-Type Signals

- No additional derived product signals were detected from repository structure.

## Source Of Truth

- `README.md` for stated project goals, setup expectations, and user-facing examples

## Supporting Doc Synthesis (Architecture)

### Confirmed

- 任务 1 统一命令入口：src/cli/task1.py (sources: `README.md`)
- 任务 2 统一命令入口：src/cli/task2.py (sources: `README.md`)

### Conflicting

- No direct architecture conflicts were synthesized from supporting docs.

### Unresolved

- No unresolved architecture items were synthesized from supporting docs.

## Referenced Historical Docs

- `README.md`

## Compatibility Boundaries

- Prefer changing source code and configuration first, then refresh `dfa-doc/AGENTS/` docs.
- Do not let generated docs drift away from the repository's actual entrypoints and workflows.

## Conflicting Signals

- No major conflicting signals were detected automatically.
