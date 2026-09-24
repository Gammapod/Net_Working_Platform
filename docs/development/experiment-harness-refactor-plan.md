# Experiment Harness Refactor Plan

This plan defines the target experiment harness model for Net Working Platform. It supersedes ad-hoc runner-specific experiment plans where those plans describe how to run LLM experiments, seed scenarios, or assemble prompts.

Legacy experiment notes remain useful as product-learning history, but they should be treated as disposable migration inputs unless this document explicitly promotes their content into the standard harness model.

## Migration Status

Current phase: **Phase 5 complete — ad-hoc runners retired from canonical use**.

Implications:

- This document is the active design reference for experiment harness work.
- New experiment work should target the standard runner families and reusable seed model below.
- Legacy experiment plans, manuals, logs, and one-off runner instructions are migration inputs, not canonical operating procedures.
- New experiment work should now use only the standard runner families. Retired runners are cataloged in `docs/development/retired-experiment-runners.md` until deletion criteria are met.

## Goals

- Maintain a small set of reusable experiment runners instead of creating a new runner for every scenario.
- Maintain reusable seed data that can be scaled up/down and consumed by multiple runner families.
- Keep agent-facing prompts assembled from centralized instruction layers.
- Keep experiment purpose, viewer/demo needs, and metrics outside agent-facing prompts.
- Emit consistent artifacts for transcripts, graph replay, summaries, and static HTML export.
- Make protocol evolution cheaper by updating a few maintained runners and seed adapters.

## Standard Runner Families

### 1. Networking-Only Runner

Canonical runner: `scripts.dev.run_networking_experiment`

Purpose:

- Explore weak discovery, contact formation, and initial negotiation requests.
- Stop before continuing into negotiation messages, match proposals, or terminal negotiation outcomes.

Runner responsibilities:

- Schedule agent turns.
- Provide visible discovery/contact/capacity context.
- Enforce protocol-valid networking actions through schema and application services.
- Emit standard run artifacts, including graph snapshots and `graph_events.jsonl`.

Non-goals:

- Do not continue negotiations after request creation.
- Do not instruct agents that opening a negotiation is an experiment endpoint.

### 2. Unified Lifecycle Runner

Canonical runner: `scripts.dev.run_unified_agent_lifecycle_experiment`

Purpose:

- Explore the full agent lifecycle: discovery, contact, negotiation request, accept/reject, messages, fact disclosure, match proposal, acceptance, closure, and defer.
- Serve as the default model-backed agent simulation runner.

Runner responsibilities:

- Schedule agent turns across active market state.
- Merge discovery/contact context with negotiation decision context.
- Expose available protocol actions without adding run-specific business goals.
- Include available fact disclosures once seed data supports disclosable profile facts.
- Emit standard run artifacts compatible with the static viewer.

### 3. Negotiation-Only Runner

Canonical runner: `scripts.dev.run_negotiation_experiment`

Purpose:

- Explore agent behavior once one or more negotiations already exist.
- Reuse pairwise-style and strategy-matrix experiments without requiring discovery/contact setup in every run.
- Focus on accept/reject, messages, fact disclosure, match proposal, acceptance, closure, and defer.

Runner responsibilities:

- Start from reusable seeds that contain requested, open, proposal-pending, or otherwise active negotiations.
- Schedule turns only among agents participating in seeded negotiations unless a seed explicitly broadens the schedule.
- Provide negotiation decision context, represented-party profile facts, and strategy/flavor context.
- Expose optional fact disclosure fields when available.
- Emit the same standard artifact family as other maintained runners.

Non-goals:

- Do not perform weak discovery or contact formation.
- Do not require every negotiation-only seed to be pairwise; pairwise is the smallest useful case, not the only shape.
- Do not preserve old pairwise runner prompts as canonical instructions; migrate reusable strategy and fact data into seeds and centralized prompt layers.

Candidate seed families:

- `pairwise-facts`;
- `pairwise-strategy-matrix`;
- `parallel-inbound-negotiations`;
- `multi-party-open-negotiations`;
- `proposal-pending-review`.

### 4. Replay / Scripted Runner

Canonical runner: `scripts.dev.run_experiment` for versioned seeds with scripted turns.

Purpose:

- Produce deterministic graph and viewer artifacts.
- Reproduce known event sequences without model variability.
- Support artifact/viewer development and debugging.

Runner responsibilities:

- Load versioned seed files.
- Execute scripted decisions through protocol services.
- Emit the same artifact family as model-backed runners.

Non-goals:

- Do not evaluate model behavior.
- Do not encode preferred market outcomes as protocol truth.

## Reusable Seed Data Model

Seed data should be independent of runner choice. A seed should describe market starting state; a runner should describe how turns are executed.

The active reusable seed catalog is maintained in `docs/development/experiment-seed-catalog.md`.

Reusable seeds should define, as applicable:

- agents;
- represented clients/principals;
- representation edges;
- weak discovery edges;
- initial agent contacts;
- initial negotiations and states;
- represented-party profile facts available for protocol disclosure;
- structured representation context for prompts;
- strategy/flavor assignments;
- scale parameters or named variants.

Target seed families:

- `viewer-showcase-small`, `viewer-showcase-medium`, `viewer-showcase-large`;
- `pairwise-facts`;
- `pairwise-strategy-matrix`;
- `parallel-inbound-negotiations`;
- `proposal-pending-review`;
- `open-market-networking`;
- `multi-party-portfolio`;
- deterministic replay/demo seeds for viewer development.

## Prompt Assembly Rules

All standard runners should use centralized prompt builders under `src/net_working_platform/experiments/`.

Prompt layers:

1. Platform action interface: protocol mechanics, output shape, currently available actions, and visible-context constraints only.
2. Representation context: structured client/principal data and simple representation responsibility.
3. Strategy/flavor instructions: reusable style and priority guidance selected by seed data.

Agent-facing prompts must not disclose that the run is an experiment, test, benchmark, demo, viewer showcase, scenario, or endpoint-oriented workflow.

## Standard Artifact Contract

Standard runners should emit:

- `summary.json`;
- `transcript.jsonl`;
- `graph_events.jsonl`;
- `initial_graph.json` and `final_graph.json`;
- `initial_graph.mmd` and `final_graph.mmd`;
- `viewer_model.json` after HTML export;
- `viewer.html` after HTML export.

Artifact records should distinguish real protocol events, raw model decisions, validation failures, defers, and skipped turns. Null decisions should not appear as unknown protocol activity in the viewer.

## Legacy / Disposable Documentation

The following documents are retained for historical observations, but their runner-specific instructions should be treated as disposable during the refactor:

- `docs/development/llm-experiment-plan.md`
- `docs/development/llm-experiment-manual.md`
- `docs/development/game-theory-experiment-plan.md`
- `docs/development/game-theory-experiment-log.md`
- `docs/development/llm-experiment-log.md`
- demo output directories under `docs/development/*-demo/`

Keep or migrate only durable concepts:

- observed model failures and missing affordances;
- reusable strategy definitions;
- scenario facts worth preserving as seeds;
- artifact/viewer requirements;
- protocol change requests.

After migration, archive or delete duplicated runner instructions and old one-off manual procedures.

## Migration Plan

### Phase 1: Declare Standards

- Treat this document as the active harness design reference.
- Mark legacy experiment plans/manuals as migration inputs.
- Keep the runner table in `experiment-scenario-catalog.md` aligned with the standard runner families.

### Phase 2: Stabilize Runner Interfaces

Status: **Complete for the initial standard runner surface.** Follow-up refinements may continue in later phases as seeds and fact disclosure are standardized.

- Give networking-only and unified lifecycle runners the same seed-selection pattern.
- Add the negotiation-only runner as a maintained standard runner for seeds that begin inside active negotiations.
- Ensure both emit the standard artifact contract.
- Move any remaining agent-facing prose out of runners and into centralized prompt builders.
- Add runner-level metadata fields: runner family, seed ID, seed variant, model, turn count, limits.

### Phase 3: Standardize Seeds

Status: **Complete for the initial reusable seed surface.** Viewer-showcase and pairwise-facts now have documented seed-family roles; viewer-showcase has variants and represented-party fact profile data.

- Extract reusable seed definitions from Python-only helpers where practical.
- Add viewer-showcase variants with scale parameters.
- Add disclosable `RepresentedPartyFact` profile data to viewer-showcase seed data.
- Ensure the same seed can be used by networking-only and unified lifecycle runners.

### Phase 4: Add Fact Disclosure To Unified Lifecycle

Status: **Complete for the initial viewer-showcase fact-profile path.** Unified lifecycle runs now pass represented-party fact profiles into negotiation services, expose available fact fields through the turn schema, and carry optional `disclose_fact_fields` into executable negotiation decisions.

- Pass represented-party fact profiles into the negotiation service.
- Include `available_fact_disclosures_by_negotiation` in unified runner schema construction.
- Permit optional `disclose_fact_fields` on substantive negotiation actions.
- Record whether models disclose facts, which facts they disclose, and whether disclosure improves negotiation quality.

### Phase 5: Retire Ad-Hoc Runners

Status: **Complete for canonical workflow retirement.** Legacy/ad-hoc runners are no longer canonical for new experiment work and are cataloged with replacement paths in `docs/development/retired-experiment-runners.md`. Physical deletion remains follow-up work once dependent tests/docs/history are migrated.

- Classify existing specialized runners as either standard, adapter, or legacy.
- Port useful scenarios to standard seeds.
- Remove or archive runners that duplicate standard runner behavior.
- Update docs to link only to maintained runner families for new experiments.

## Open Questions

- Should seed files become JSON-first, Python-first, or mixed with Python generators for scale?
- What is the smallest stable schema for represented-party profile facts across clients and principals?
- Should model/provider configuration be a runner argument, a run manifest, or both?
- How should standard runners support multi-provider comparisons without duplicating run logic?
