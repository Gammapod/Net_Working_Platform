# Retired Experiment Runners

This document records experiment runners that are no longer canonical after the experiment harness refactor.

Retired does not mean immediately deleted. It means:

- do not use the runner for new experiment design;
- do not add new scenario logic to it;
- migrate useful seed data, observations, or mechanics into standard runners and reusable seeds;
- delete the runner once no tests, docs, or historical reproduction needs depend on it.

Canonical replacement runners are defined in `experiment-harness-refactor-plan.md`.

## Standard Runners For New Work

Use these for new experiments:

- `scripts.dev.run_networking_experiment` — networking-only runs.
- `scripts.dev.run_unified_agent_lifecycle_experiment` — full lifecycle model-backed runs.
- `scripts.dev.run_negotiation_experiment` — negotiation-only runs from active negotiation seeds.
- `scripts.dev.run_experiment` — replay/scripted runs from versioned seed files.

## Retired / Legacy Runners

| Retired runner | Replacement path | Migration note |
| --- | --- | --- |
| `scripts.dev.run_supervised_llm_experiment` | `scripts.dev.run_negotiation_experiment` for active negotiation decisions; `scripts.dev.run_unified_agent_lifecycle_experiment` for lifecycle runs | Preserve context-shape lessons and schema-constrained provider mechanics only. |
| `scripts.dev.run_scaled_experiment` | standard seed variants plus unified lifecycle or replay/scripted runner | Port useful market scale parameters into reusable seeds/generators. |
| `scripts.dev.run_pairwise_strategy_experiment` | `scripts.dev.run_negotiation_experiment --scenario pairwise-facts` | Core smoke coverage has migrated to the negotiation-only runner. Preserve any remaining strategy-matrix cases as seed variants; do not preserve runner-specific prompt prose. |
| `scripts.dev.run_weak_discovery_experiment` | `scripts.dev.run_networking_experiment` | Port useful discovery scenarios into networking seed variants. |
| `scripts.dev.run_topic_selection_networking_experiment` | reusable portfolio seeds plus networking/unified runners | Port topic data into structured representation context and fact profiles. |
| `scripts.dev.run_partial_topic_proposal_experiment` | negotiation-only or unified lifecycle runner with multi-party portfolio seeds | Port useful two-stage topic affordances into seed data and context-shape requirements. |

## Adapter Candidate

`scripts.dev.run_bandwidth_sweep_experiment` remains as a thin adapter over `scripts.dev.run_unified_agent_lifecycle_experiment`. It accepts the standard scenario/seed-variant selector and must not define its own prompt or scenario semantics. If it grows scenario-specific behavior, migrate that behavior into reusable seed variants instead.

## Deletion Criteria

A retired runner can be deleted when:

1. its useful seed/scenario data has been migrated to `experiment-seed-catalog.md` or a versioned seed/generator;
2. its useful observations have been migrated to current docs or issues;
3. no maintained tests import it;
4. no active runbook or standard workflow references it;
5. any desired historical outputs have been archived outside the active harness docs.

## Current Follow-Ups

- Migrate remaining pairwise strategy matrix coverage to `scripts.dev.run_negotiation_experiment` seed variants.
- Convert useful scaled-market parameters into reusable seed variants or generators.
- Decide whether bandwidth sweep remains as a thin adapter around standard runners.
