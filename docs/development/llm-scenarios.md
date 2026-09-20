# LLM Scenario Development Utilities

This document describes dev/test-only utilities for creating known states that can be shown to a real LLM during supervised experiments.

These utilities are not production CLI behavior. They live under `tests/support/` and are intended for tests, local experiments, and repeatable scenario setup while the agent runtime is still deferred.

## Current Scenario: Inbound Request

Helper:

```python
from tests.support.llm_scenarios import seed_inbound_request_scenario
```

The helper creates this state:

- `agent_1` and `agent_2` exist.
- `agent_1` has an active connection to `agent_2`.
- `agent_1` opens a requested negotiation with `agent_2`.
- The returned scenario includes `agent_2`'s read-only decision context.

The context is suitable for a first supervised LLM decision prompt because it contains:

- active load
- inbound requested negotiations
- open negotiations
- recent protocol events

## Intended Experiment Shape

Use one decision at a time:

1. Seed a known scenario in a temporary database.
2. Give the LLM the read-only decision context.
3. Restrict the model response to one validated action enum plus arguments.
4. Execute the selected action through application services or CLI.
5. Verify the resulting event history against functional invariants.

Do not give the LLM direct database access. Do not start with autonomous loops.

## Current Supervised Execution Test

`test_supervised_llm_accept_experiment_validates_executes_and_records_event` simulates the first end-to-end supervised experiment without calling a live model:

1. Seed the inbound request scenario.
2. Use a simulated LLM JSON decision: `accept_negotiation`.
3. Validate the JSON through the LLM decision contract.
4. Execute the validated decision through application services.
5. Verify that the negotiation response event is recorded.

This proves the safety path before introducing a real model into the loop.
