# Project Overview

## What This Project Is

- 这个目录实现了赛题任务 1 的一个最小可运行版本：把原始文本候选池转成标准化事件表，供统计同学直接接手。
- Current repo shape: `Unknown/Unclassified Repository`.

## Top Rules (Read First)

- Rule 1: State repository scope and user value as explicit rules before writing broad product narrative.
- Rule 2: Use lifecycle language (`init/refresh/doctor/migrate`) to keep docs maintainable over one-shot generation.

## Document Contract

- This page is maintainer-facing source-of-truth for its domain; keep it synchronized with `dfa-doc/AGENTS/` in dual mode and `dfa-doc/handbook/` as the human-view root.
- Update this page in the same PR as behavior changes; avoid narrative-only refreshes without command or contract changes.
- Record scope decisions as explicit rules and owners; move stale discussion text to decision backlog.

## Dual Sync Checklist

- After edits, refresh in dual mode and verify both `dfa-doc/AGENTS/` and `dfa-doc/handbook/` were updated in the same change set.
- If one side changed without the other, treat it as documentation drift and resolve before merge.
- When scope or audience changes, update project positioning and retention rules in both doc systems together.

## Paired Refresh Rules

- Refresh contract: run one refresh/generate action that updates paired views together; do not patch one locale/audience in isolation.
- Path contract: verify changed files include both `dfa-doc/AGENTS*/` and `dfa-doc/handbook*/` counterparts when behavior changes affect shared source-of-truth.
- Quad-mode contract: when using `--output-mode quad`, validate all four roots (`dfa-doc/AGENTS/`, `dfa-doc/AGENTS.zh/`, `dfa-doc/handbook/`, `dfa-doc/handbook.zh/`) in the same review cycle.
- Product pairing rule: if `dfa-doc/handbook/overview.md` changes due to scope/value decisions, refresh paired product paths under both AGENTS roots.

## Dual Pairing Contract (Rules)

- Pairing mode rule: in `dual`, human and agent docs are generated from one analysis pass and must be reviewed as one change set.
- Locale-output rule: human locale `en` maps to `dfa-doc/handbook/`.
- Template rule: human template variant `paired-core` is part of the pairing contract and must remain consistent across paired docs.
- Path pair rule: `dfa-doc/handbook/overview.md` pairs with `dfa-doc/AGENTS/01-product/001-core-goals.md` for agent-facing product rules and scope guardrails.
- Path pair rule: `dfa-doc/handbook/overview.md` pairs with `dfa-doc/AGENTS/01-product/002-prd.md` for agent-facing user and outcome contract.
- Path pair rule: `dfa-doc/handbook/overview.md` pairs with `dfa-doc/AGENTS/01-product/003-app-flow.md` for agent-facing flow and entry-surface notes.

## Paired Agent Docs (Dual Mode)

- `dfa-doc/AGENTS/01-product/001-core-goals.md` for agent-facing product rules and scope guardrails.
- `dfa-doc/AGENTS/01-product/002-prd.md` for agent-facing user and outcome contract.
- `dfa-doc/AGENTS/01-product/003-app-flow.md` for agent-facing flow and entry-surface notes.

## Output Boundary (Human vs Agent)

- Use `dfa-doc/handbook/` for maintainer-facing policy and decisions; use `dfa-doc/AGENTS/` for execution order, command wiring, and handoff runbooks.
- If a change affects both reader types, update both systems in one dual refresh cycle instead of patching only one side.
- Keep user/value framing in `dfa-doc/handbook/overview.md`; keep edit-time operating rules in `dfa-doc/AGENTS/product.md` (or layered product docs).

## Dual View Rationale

- `dfa-doc/handbook/` and `dfa-doc/AGENTS/` are two views generated from the same repository analysis and source-of-truth anchors.
- When the two views diverge, treat it as refresh drift rather than independent documentation authority.
- Product intent lives in `dfa-doc/handbook/overview.md`, while execution-facing preservation rules live in paired `dfa-doc/AGENTS/` product docs.

## Intended Audience

- Repository maintainers responsible for day-to-day delivery and operational stability.

## Key Entry Points

- No clear routes or invocation entrypoints were detected automatically.

## Synthesis Summary

- Sources analyzed: `1`
- Synthesized statements: `0` confirmed, `0` conflicting, `0` unresolved

## Knowledge Status

### Confirmed Rules

- No direct product facts were synthesized from supporting docs.

### Supporting Signals

- Project intent from README/code signals: 这个目录实现了赛题任务 1 的一个最小可运行版本：把原始文本候选池转成标准化事件表，供统计同学直接接手。

### Decision Backlog

- No unresolved product items were synthesized from supporting docs.

### Conflict Watchlist

- No direct product conflicts were synthesized from supporting docs.

## Current Priorities

- Capture latest decisions in `dfa-doc/handbook/` and keep `dfa-doc/AGENTS/` synchronized after changes.

## Documentation Gaps To Close

- No major product documentation gaps were detected from supporting sources.

## Update Triggers

- When new user-facing routes, commands, or APIs are added, update scope and audience notes.
- When priorities change in release planning, update the project overview and open decision list.

## Maintenance Workflow

- Assign one maintainer owner for this document and update it in the same pull request as behavior changes.
- Review this document at least once per sprint or before each release cut.
- Update after roadmap, target user, or feature scope decisions.
- No major synthesis conflicts were detected; focus on keeping this page current with implementation changes.

## Bootstrap Backlog (When Docs Are Thin)

- Supporting docs were found; continue consolidating them into this page and archive stale duplicates.

## Provenance

- `README.md`
