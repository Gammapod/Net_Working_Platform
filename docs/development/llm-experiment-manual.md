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

It creates an inbound requested negotiation for `agent_2` and returns `agent_2`'s decision context.

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
