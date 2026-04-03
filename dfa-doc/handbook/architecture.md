# Architecture

## Source Of Truth

- `README.md` for stated project goals, setup expectations, and user-facing examples

## Top Rules (Read First)

- Rule 1: Resolve source-of-truth conflicts before changing CLI, adapter, or build-path behavior.
- Rule 2: Treat platform adapters as distribution details; keep contract changes centralized at CLI entry.

## Document Contract

- This page is maintainer-facing source-of-truth for its domain; keep it synchronized with `dfa-doc/AGENTS/` in dual mode and `dfa-doc/handbook/` as the human-view root.
- Update this page in the same PR as behavior changes; avoid narrative-only refreshes without command or contract changes.
- Resolve source-of-truth conflicts before editing CLI, adapter, or build-path behavior.

## Dual Sync Checklist

- After edits, refresh in dual mode and verify both `dfa-doc/AGENTS/` and `dfa-doc/handbook/` were updated in the same change set.
- If one side changed without the other, treat it as documentation drift and resolve before merge.
- When source-of-truth files move, update references in both doc systems before adjusting adapter/build-path rules.

## Paired Refresh Rules

- Refresh contract: run one refresh/generate action that updates paired views together; do not patch one locale/audience in isolation.
- Path contract: verify changed files include both `dfa-doc/AGENTS*/` and `dfa-doc/handbook*/` counterparts when behavior changes affect shared source-of-truth.
- Quad-mode contract: when using `--output-mode quad`, validate all four roots (`dfa-doc/AGENTS/`, `dfa-doc/AGENTS.zh/`, `dfa-doc/handbook/`, `dfa-doc/handbook.zh/`) in the same review cycle.
- Architecture pairing rule: if `dfa-doc/handbook/architecture.md` changes due to boundary/source-of-truth updates, refresh paired architecture paths under both AGENTS roots.

## Dual Pairing Contract (Rules)

- Pairing mode rule: in `dual`, human and agent docs are generated from one analysis pass and must be reviewed as one change set.
- Locale-output rule: human locale `en` maps to `dfa-doc/handbook/`.
- Template rule: human template variant `paired-core` is part of the pairing contract and must remain consistent across paired docs.
- Path pair rule: `dfa-doc/handbook/architecture.md` pairs with `dfa-doc/AGENTS/02-architecture/004-tech-stack.md` for stack facts and platform anchors.
- Path pair rule: `dfa-doc/handbook/architecture.md` pairs with `dfa-doc/AGENTS/02-architecture/007-architecture-compatibility.md` for source-of-truth and compatibility rules.

## Paired Agent Docs (Dual Mode)

- `dfa-doc/AGENTS/02-architecture/004-tech-stack.md` for stack facts and platform anchors.
- `dfa-doc/AGENTS/02-architecture/007-architecture-compatibility.md` for source-of-truth and compatibility rules.

## Output Boundary (Human vs Agent)

- Use `dfa-doc/handbook/` for maintainer-facing policy and decisions; use `dfa-doc/AGENTS/` for execution order, command wiring, and handoff runbooks.
- If a change affects both reader types, update both systems in one dual refresh cycle instead of patching only one side.
- Keep architecture rationale in `dfa-doc/handbook/architecture.md`; keep CLI/build/source-of-truth guardrails in `dfa-doc/AGENTS/architecture.md` (or layered architecture docs).

## Dual View Rationale

- `dfa-doc/handbook/` and `dfa-doc/AGENTS/` are two views generated from the same repository analysis and source-of-truth anchors.
- When the two views diverge, treat it as refresh drift rather than independent documentation authority.
- Architecture rationale lives in `dfa-doc/handbook/architecture.md`, while operational boundaries for agents live in paired `dfa-doc/AGENTS/` architecture docs.

## Detected Signals

- No additional derived product signals were detected from repository structure.

## System Map

- No system map details were detected automatically.

## Synthesis Summary

- Sources analyzed: `1`
- Synthesized statements: `2` confirmed, `0` conflicting, `0` unresolved

## Knowledge Status

### Confirmed Rules

- 任务 1 统一命令入口：src/cli/task1.py
- 任务 2 统一命令入口：src/cli/task2.py

### Supporting Signals

- No additional derived product signals were detected from repository structure.

### Decision Backlog

- No unresolved architecture items were synthesized from supporting docs.

### Conflict Watchlist

- No direct architecture conflicts were synthesized from supporting docs.

## Stability Boundaries

- Treat source-of-truth files as canonical when supporting docs disagree.
- Refresh both `dfa-doc/handbook/` and `dfa-doc/AGENTS/` after architecture-impacting changes.

## Update Triggers

- When source-of-truth files, service boundaries, or runtime dependencies change, update this page.
- When integration contracts change (routes/endpoints/storage), refresh architecture notes in the same PR.

## Maintenance Workflow

- Assign one maintainer owner for this document and update it in the same pull request as behavior changes.
- Review this document at least once per sprint or before each release cut.
- Update after boundary, dependency, or interface contract changes.
- No major synthesis conflicts were detected; focus on keeping this page current with implementation changes.

## Bootstrap Backlog (When Docs Are Thin)

- Supporting docs were found; continue consolidating them into this page and archive stale duplicates.

## Provenance

- `README.md`
