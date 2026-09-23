# Area Ownership

This document defines the working ownership model for Net Working Platform. It is intended to make repository stewardship, protocol engineering, and experimentation separable while keeping the project coherent.

## Ownership Principles

- Repository health is a product concern. Documentation, infrastructure, dependencies, tests, and source layout should remain aligned with the MVP goal.
- Protocol behavior becomes normative only through `docs/source-of-truth/functional-invariants.md` and deterministic tests under `tests/`.
- Experiments are advisory. Experiment results may motivate platform changes, but they do not define platform behavior until an invariant and test protect that behavior.
- Agent scopes should be narrow by default. Cross-area changes require Repository-Owner coordination.

## Roles

### Repository-Owner

Repository-Owner is accountable for the project as a coherent product and engineering system.

Primary responsibilities:

- Maintain repository-wide structure and ownership boundaries.
- Steward `README.md`, planning docs, ownership docs, and infrastructure docs.
- Own dependency and infrastructure decisions, including test runner setup, lint/type tooling, packaging, and agent configuration.
- Coordinate Platform+Protocol-Owner and Experiment-Owner work.
- Resolve cross-area tradeoffs and decide when experiment findings become protocol work.

Primary write scope:

- Entire repository, with conservative use of broad authority.
- Especially `README.md`, `docs/planning/`, `docs/ownership/`, `pyproject.toml`, `.opencode/`, and repository infrastructure.

### Platform+Protocol-Owner

Platform+Protocol-Owner owns deterministic platform behavior and follows the invariant-driven TDD workflow for behavior changes.

Primary responsibilities:

- Maintain domain rules, application services, storage/repository behavior, migrations, deterministic CLI behavior, and provider/execution guarantees.
- Update `docs/source-of-truth/functional-invariants.md` before implementing new or changed behavior.
- Add or update tests that protect invariant IDs.
- Keep CLI behavior thin over application services.
- Keep infrastructure concerns out of the domain layer.
- Prevent experiment-specific outcomes from becoming hidden protocol rules.

Primary write scope:

- `src/net_working_platform/domain/`
- `src/net_working_platform/application/`
- `src/net_working_platform/storage/`
- `src/net_working_platform/cli.py`
- `migrations/`
- `tests/` when protecting deterministic invariants or deterministic tooling behavior
- `docs/source-of-truth/`
- Protocol-affecting updates to `README.md` or planning docs, coordinated with Repository-Owner

### Experiment-Owner

Experiment-Owner owns exploratory product learning and experiment scenario design without owning protocol implementation.

Primary responsibilities:

- Design experiments that explore platform/product outcomes.
- Maintain experiment plans, manuals, logs, strategy catalogs, and scenario notes.
- Maintain scenario seed data and test setup used for experiments.
- Identify missing affordances or unclear context exposed by the platform.
- Request protocol/platform changes from Repository-Owner or Platform+Protocol-Owner instead of implementing them directly.

Primary write scope:

- `docs/development/` experiment plans, manuals, logs, and strategy catalogs
- Experiment scenario definitions and seed data under `src/net_working_platform/experiments/` when those files do not implement protocol behavior or execution guarantees
- Experiment-support setup under `tests/support/` when used to create deterministic experiment fixtures

Read-only or request-only scope:

- `docs/source-of-truth/`
- `src/net_working_platform/domain/`
- `src/net_working_platform/application/`
- `src/net_working_platform/storage/`
- `src/net_working_platform/cli.py`
- `migrations/`
- provider adapters, runners, and other tooling that enforce protocol execution guarantees

## Tests And Experiments Boundary

`tests/` protects deterministic platform behavior. It may test experiment tooling mechanics, but it must not protect preferred product outcomes from specific scenarios.

Appropriate tests include:

- domain transition rules;
- application-service invariants;
- schema/repository behavior;
- CLI output contracts;
- provider/LLM decision contract validation;
- experiment runner mechanics such as actor focus, valid-action enforcement, and artifact writing.

Inappropriate tests include:

- asserting that a particular strategy should win;
- asserting that a model should choose a specific business outcome;
- encoding a preferred match quality judgment as a platform invariant;
- treating one experiment scenario's outcome as normative platform behavior.

`experiments/` explores product outcomes. Experiment observations should be recorded in development docs and may become implementation requests. They become platform obligations only after Platform+Protocol-Owner or Repository-Owner updates the source-of-truth invariants and protects the behavior with deterministic tests.

## Request Flow

1. Experiment-Owner records an observation or missing affordance in the relevant experiment log or plan.
2. Experiment-Owner files or states a platform request with the observed issue, affected scenario, and desired measurable platform affordance.
3. Repository-Owner decides whether the request aligns with the MVP and assigns it to Platform+Protocol-Owner when appropriate.
4. Platform+Protocol-Owner follows invariant-driven TDD before changing protocol or tooling behavior.
5. Repository-Owner verifies documentation, ownership boundaries, dependencies, and repository coherence before the work is considered complete.

## Extension Pattern

When the project grows, add new owners only when there is a stable boundary with distinct responsibilities and file ownership. Candidate future owners include Documentation/Product Steward and Infrastructure/Quality Owner. Until then, Repository-Owner explicitly includes documentation stewardship and infrastructure ownership.
