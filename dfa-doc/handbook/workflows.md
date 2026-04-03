# Workflows

## Top Rules (Read First)

- Rule 1: Verification gate: workflow changes are not complete until `python3 src/cli/task1.py check` pass.
- Rule 2: Verification order: 1) `python3 src/cli/task1.py check`; stop at the first failing command before running later checks.
- Rule 3: Failure triage priority: 1) rerun the first failing gate (`python3 src/cli/task1.py check`) to isolate command scope; 2) if failures persist, roll back generated docs to last known-good state and rerun `docagent refresh`.

## Document Contract

- This page is maintainer-facing source-of-truth for its domain; keep it synchronized with `dfa-doc/AGENTS/` in dual mode and `dfa-doc/handbook/` as the human-view root.
- Update this page in the same PR as behavior changes; avoid narrative-only refreshes without command or contract changes.
- Keep setup/run/verify/triage order executable from a clean checkout before marking this page done.

## Dual Sync Checklist

- After edits, refresh in dual mode and verify both `dfa-doc/AGENTS/` and `dfa-doc/handbook/` were updated in the same change set.
- If one side changed without the other, treat it as documentation drift and resolve before merge.
- Run documented verify commands after refresh and keep failure-triage order aligned across both doc systems.

## Paired Refresh Rules

- Refresh contract: run one refresh/generate action that updates paired views together; do not patch one locale/audience in isolation.
- Path contract: verify changed files include both `dfa-doc/AGENTS*/` and `dfa-doc/handbook*/` counterparts when behavior changes affect shared source-of-truth.
- Quad-mode contract: when using `--output-mode quad`, validate all four roots (`dfa-doc/AGENTS/`, `dfa-doc/AGENTS.zh/`, `dfa-doc/handbook/`, `dfa-doc/handbook.zh/`) in the same review cycle.
- Execution pairing rule: if `dfa-doc/handbook/workflows.md` changes due to command/order updates, refresh paired execution paths under both AGENTS roots.

## Dual Pairing Contract (Rules)

- Pairing mode rule: in `dual`, human and agent docs are generated from one analysis pass and must be reviewed as one change set.
- Locale-output rule: human locale `en` maps to `dfa-doc/handbook/`.
- Template rule: human template variant `paired-core` is part of the pairing contract and must remain consistent across paired docs.
- Path pair rule: `dfa-doc/handbook/workflows.md` pairs with `dfa-doc/AGENTS/03-execution/008-implementation-plan.md` for setup, verify, and failure-triage order.

## Paired Agent Docs (Dual Mode)

- `dfa-doc/AGENTS/03-execution/008-implementation-plan.md` for setup, verify, and failure-triage order.

## Output Boundary (Human vs Agent)

- Use `dfa-doc/handbook/` for maintainer-facing policy and decisions; use `dfa-doc/AGENTS/` for execution order, command wiring, and handoff runbooks.
- If a change affects both reader types, update both systems in one dual refresh cycle instead of patching only one side.
- Keep maintainer runbook context in `dfa-doc/handbook/workflows.md`; keep step-by-step agent execution plan in `dfa-doc/AGENTS/workflows.md` (or layered execution docs).

## Dual View Rationale

- `dfa-doc/handbook/` and `dfa-doc/AGENTS/` are two views generated from the same repository analysis and source-of-truth anchors.
- When the two views diverge, treat it as refresh drift rather than independent documentation authority.
- Maintainer runbook context lives in `dfa-doc/handbook/workflows.md`, while step ordering for agent actions lives in paired `dfa-doc/AGENTS/` execution docs.

## Setup

```bash
Review README setup steps and install dependencies with the repository's package manager.
```

## Run

```bash
Run the main local command from README examples.
```

## Verify

```bash
Run verification commands from CI or README (lint/test/build equivalents).
```

## Synthesis Summary

- Sources analyzed: `1`
- Synthesized statements: `4` confirmed, `0` conflicting, `0` unresolved

## Knowledge Status

### Confirmed Rules

- Verification gate: workflow changes are not complete until `python3 src/cli/task1.py check` pass.
- Verification order: 1) `python3 src/cli/task1.py check`; stop at the first failing command before running later checks.
- Failure triage priority: 1) rerun the first failing gate (`python3 src/cli/task1.py check`) to isolate command scope; 2) if failures persist, roll back generated docs to last known-good state and rerun `docagent refresh`.
- Run `python3 src/cli/task1.py check`

### Supporting Signals

- Primary command workflow centers on `npm` package scripts and repository-local verify commands.

### Decision Backlog

- No unresolved execution items were synthesized from supporting docs.

### Conflict Watchlist

- No direct execution conflicts were synthesized from supporting docs.

## Operational Notes

- Keep command examples in this file aligned with CI and README instructions.

## Update Triggers

- When setup/run/verify commands change, update this runbook immediately.
- When CI checks or release gates change, sync the Verify and Operational Notes sections.

## Maintenance Workflow

- Assign one maintainer owner for this document and update it in the same pull request as behavior changes.
- Review this document at least once per sprint or before each release cut.
- Update after setup/run/verify command changes or CI workflow updates.
- No major synthesis conflicts were detected; focus on keeping this page current with implementation changes.

## Bootstrap Backlog (When Docs Are Thin)

- Supporting docs were found; continue consolidating them into this page and archive stale duplicates.

## Provenance

- `README.md`
