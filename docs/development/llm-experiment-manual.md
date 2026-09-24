# LLM Experiment Manual

This manual defines the repeatable process for supervised LLM experiments against Net Working Platform.

The goal is to observe model decisions while preserving the product protocol invariants. Experiments must keep the model behind a validated decision contract and must execute decisions through application services.

## Safety Rules

- Give the model read-only decision context only.
- Do not give the model database credentials or direct database access.
- Do not allow free-form command execution.
- Require exactly one JSON decision object as output.
- Validate model output with the LLM decision contract before execution.
- Execute validated decisions through application services only.
- Start with one decision at a time. Do not start with autonomous loops.
- Record raw model output and validation/execution results in the experiment log.

## Agent Instruction Layering

Agent-facing instructions should be assembled from reusable layers, not written ad hoc inside runner-specific prompts.

1. **Platform-level instructions** describe Net Working Platform action mechanics only: the actor identity, currently available protocol actions, required JSON response shape, and protocol constraints such as using only visible context. This layer must be agent-type agnostic and must not state business goals, strategy preferences, experiment endpoints, or preferred market outcomes.
2. **Representation context** describes the clients or principals represented by the scheduled agent using structured fields. It may include simple representation-responsibility statements such as matching represented clients to relevant openings or finding relevant candidates for represented principals. Priority information should be represented as data fields whenever possible.
3. **Strategy/flavor instructions** describe reusable representative style, such as speed, evidence threshold, contact maintenance, negotiation posture, and what signals to weight or ignore. These instructions should be selected by scenario data and shared across experiments instead of embedded directly in runners.

Agent-facing prompts must not disclose that the run is an experiment, test, demo, viewer showcase, benchmark, or scenario. They also must not tell the agent to satisfy an experimental endpoint, form a specific kind of contact, prefer a specific target category, or optimize for graph/viewer output. Experiment purpose belongs in run documentation and logs, not in the prompt shown to the agent. Agents should receive the same kind of representation context they would receive if acting for real represented parties.

Experiment runners may still enforce schedules, action schemas, capacity limits, and validation outside the prompt. Those controls are runner/protocol mechanics; they should not be converted into agent-facing business objectives.

## Standard Experiment Flow

1. Select or seed a known scenario.
2. Retrieve read-only decision context for the observing agent.
3. Provide the model with the prompt template and context.
4. Require one JSON decision object.
5. Parse and validate the decision with `parse_llm_decision`.
6. Execute the validated decision with `execute_llm_decision`.
7. Verify resulting state and event history against functional invariants.
8. Record observations in `docs/development/llm-experiment-log.md`.

## Current Scenario Utility

The current dev/test scenario helper is:

```python
from tests.support.llm_scenarios import seed_inbound_request_scenario
```

It creates an inbound requested negotiation for `agent_2` and returns `agent_2`'s decision context. Experiment context packages include explicit capacity fields:

- `active_load`
- `max_active_negotiations`
- `capacity_remaining`

## Prompt Template

Use this template for the first supervised experiments:

```text
You are acting as the representative agent identified by agent_id in the decision context.

You may choose exactly one protocol decision. Return only one JSON object.
Do not include markdown, commentary, or extra keys.

Allowed actions are defined by the LLM Decision Contract:
- accept_negotiation
- reject_negotiation
- send_message
- propose_match
- accept_match
- close_negotiation
- defer

For this experiment, prefer one of:
- accept_negotiation
- reject_negotiation
- defer

Decision context:
<CONTEXT_JSON>

Return one JSON object now.
```

## Initial Allowed Execution Set

The validator accepts the full contract, but the executor currently supports only:

- `accept_negotiation`
- `reject_negotiation`
- `defer`

Other valid contract actions should not be used in execution experiments until executor support is added.

## Dev Experiment Runner

The current dev-only runner is:

```powershell
python -m scripts.dev.run_supervised_llm_experiment `
  --db-url "sqlite+pysqlite:///network.db" `
  --decision-json '{"action":"accept_negotiation","negotiation_id":"negotiation_inbound_request","actor_agent_id":"agent_2"}' `
  --pretty
```

The runner:

1. Seeds the inbound request scenario.
2. Validates the provided decision JSON.
3. Executes the validated decision through application services.
4. Emits a structured result document.

The `structured_event_log` field is backed by actual database `protocol_events` read through `SqlProtocolEventRepository`. This is the same persistence source that should back agent/user-facing history views.

### Context-Only Provider-Agnostic Loop

Use `--context-only` to generate a prompt/context package without validating or executing a model decision:

```powershell
python -m scripts.dev.run_supervised_llm_experiment `
  --db-url "sqlite+pysqlite:///network.db" `
  --context-only `
  --pretty
```

Manual multi-provider loop:

1. Run the context-only command.
2. Copy the emitted prompt/context package to the provider UI or external tool of choice.
3. Save the provider's raw JSON decision to a local file such as `decision.json`.
4. Run the executor path:

```powershell
python -m scripts.dev.run_supervised_llm_experiment `
  --db-url "sqlite+pysqlite:///network.db" `
  --decision-file decision.json `
  --use-existing-scenario `
  --pretty
```

Do not store provider API keys in this repository. Until provider adapters are introduced, provider choice happens outside this repository by selecting which external UI or tool receives the context package.

Use `--use-existing-scenario` when executing a decision after `--context-only` against the same database. This avoids reseeding the scenario and preserves one continuous experiment event log.

### JSON Schema Output Constraint

The context package includes:

- `llm_decision_json_schema`
- `response_format`

When a provider supports JSON Schema structured output, use this schema as the primary output constraint. The prose prompt is a fallback and should not be the only constraint when schema enforcement is available.

The schema mirrors `docs/source-of-truth/llm-decision-contract.md` and is exposed in code as `LLM_DECISION_JSON_SCHEMA`.

### OpenAI Schema-Constrained Adapter

A dev-only OpenAI adapter exists at:

```python
from scripts.dev.openai_provider import request_openai_decision
```

It uses the OpenAI Responses API with `text.format.type = "json_schema"`, passing `LLM_DECISION_JSON_SCHEMA` as the strict output schema. The adapter reads credentials from `OPENAI_API_KEY` unless an explicit API key is passed by tests.

This adapter is for supervised experiments only. It is not part of the production CLI or application service layer.

## Observation Guidelines

For each run, record:

- date
- model or decision source
- scenario
- prompt/manual version or summary
- decision context summary
- raw model output
- validation result
- execution result
- resulting event history
- observations
- follow-ups

## Updating This Manual

Update this manual when any of these change:

- decision context shape
- LLM decision contract
- supported executor actions
- scenario utilities
- safety rules
- experiment logging expectations
