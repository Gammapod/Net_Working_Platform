# LLM Experiment Log

This log records supervised LLM decision experiments. Entries should be append-only except for correcting factual errors.

## Entry Template

```text
## YYYY-MM-DD: Experiment Name

Model or decision source:
Scenario:
Prompt/manual reference:
Decision context summary:
Raw model output:
Validation result:
Execution result:
Resulting event history:
Observations:
Follow-ups:
```

## 2026-09-19: Inbound Request Accept Dry Run

Model or decision source: Repository-Owner assistant-mediated supervised dry run; no external model API call.

Scenario: Dev/test inbound request scenario from `seed_inbound_request_scenario`.

Prompt/manual reference: `docs/development/llm-experiment-manual.md`, initial prompt template.

Decision context summary:

- observing agent: `agent_2`
- active load: `1`
- inbound requested negotiation: `negotiation_inbound_request`
- subject: `{"role": "engineer", "location": "remote"}`
- recent event: `open_negotiation_request` from `agent_1`

Raw model output:

```json
{
  "action": "accept_negotiation",
  "negotiation_id": "negotiation_inbound_request",
  "actor_agent_id": "agent_2"
}
```

Validation result: Passed through `parse_llm_decision`; parsed action was `accept_negotiation`.

Execution result: Passed through `execute_llm_decision`; result was `{"executed": true, "action": "accept_negotiation"}`.

Resulting event history:

```json
[
  {
    "type": "open_negotiation_request",
    "actor_agent_id": "agent_1",
    "negotiation_id": "negotiation_inbound_request",
    "payload": {
      "to_agent_id": "agent_2",
      "subject": {
        "role": "engineer",
        "location": "remote"
      }
    }
  },
  {
    "type": "open_negotiation_response",
    "actor_agent_id": "agent_2",
    "negotiation_id": "negotiation_inbound_request",
    "payload": {
      "decision": "accept"
    }
  }
]
```

Observations:

- The existing harness can run the full supervised path from scenario context to validated decision execution.
- The event history confirms normal application-service behavior and preserves protocol traceability.
- This was a dry run using the assistant as the decision source, not an external model integration.

Follow-ups:

- Add an external model invocation harness or manual copy/paste workflow for a real model run.
- Record raw external model output exactly as emitted before validation.

Runner update:

- A dev-only runner now exists at `scripts/dev/run_supervised_llm_experiment.py`.
- Runner output includes `structured_event_log`, sourced from persisted `protocol_events`.

## 2026-09-19: GPT-4o Mini Inbound Request Decision

Model or decision source: OpenAI `gpt-4o-mini-2024-07-18` through the Responses API.

Scenario: Dev/test inbound request scenario from `seed_inbound_request_scenario`.

Prompt/manual reference: `docs/development/llm-experiment-manual.md`, provider-agnostic context package plus explicit executable schema reminder.

Decision context summary:

- observing agent: `agent_2`
- active load: `1`
- inbound requested negotiation: `negotiation_inbound_request`
- subject: `{"role": "engineer", "location": "remote"}`
- recent event: `open_negotiation_request` from `agent_1`

Raw model output from successful constrained accept/reject run:

```json
{"action":"accept_negotiation","negotiation_id":"negotiation_inbound_request","actor_agent_id":"agent_2"}
```

Validation result: Passed through `parse_llm_decision`; parsed action was `accept_negotiation`.

Execution result: Passed through `execute_decision_against_existing_scenario`; result was `{"executed": true, "action": "accept_negotiation"}`.

Resulting event history:

```json
[
  {
    "type": "open_negotiation_request",
    "actor_agent_id": "agent_1",
    "negotiation_id": "negotiation_inbound_request",
    "payload": {
      "to_agent_id": "agent_2",
      "subject": {
        "role": "engineer",
        "location": "remote"
      }
    }
  },
  {
    "type": "open_negotiation_response",
    "actor_agent_id": "agent_2",
    "negotiation_id": "negotiation_inbound_request",
    "payload": {
      "decision": "accept"
    }
  }
]
```

Observations:

- The first live request authenticated successfully but used `max_output_tokens=5`, which OpenAI rejected because the minimum is `16`.
- An unconstrained run returned malformed contract output missing required fields.
- A schema-reminder run chose `defer`, exposing a harness issue: `execute_decision_against_existing_scenario` currently requires `negotiation_id` before dispatch, even though `defer` does not need one.
- A constrained accept/reject run returned valid decision JSON, passed validation, executed through application services, and produced the expected database-backed event log.

Follow-ups:

- Fixed existing-scenario execution so valid `defer` decisions can execute without requiring `negotiation_id`.
- Strengthen the prompt package with action-specific schemas before broader provider comparisons.
- Consider adding optional provider adapters only after the manual loop is stable across multiple providers.

## 2026-09-19: GPT-4o Mini Schema-Constrained Adapter Decision

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Scenario: Dev/test inbound request scenario from `seed_inbound_request_scenario`.

Prompt/manual reference: `docs/development/llm-experiment-manual.md`, context package prompt plus OpenAI Responses API JSON Schema response format.

Decision context summary:

- observing agent: `agent_2`
- active load: `1`
- inbound requested negotiation: `negotiation_inbound_request`
- subject: `{"role": "engineer", "location": "remote"}`
- recent event: `open_negotiation_request` from `agent_1`

Validated decision:

```json
{
  "action": "defer",
  "actor_agent_id": "agent_2",
  "reason": "Currently at capacity and need more time to evaluate the request."
}
```

Validation result: Passed through `parse_llm_decision`; parsed action was `defer`.

Execution result: Passed through `execute_decision_against_existing_scenario`; result was non-mutating: `{"executed": false, "action": "defer"}`.

Resulting event history:

```json
[
  {
    "type": "open_negotiation_request",
    "actor_agent_id": "agent_1",
    "negotiation_id": "negotiation_inbound_request",
    "payload": {
      "to_agent_id": "agent_2",
      "subject": {
        "role": "engineer",
        "location": "remote"
      }
    }
  }
]
```

Observations:

- The first live schema attempt exposed an adapter bug: timeout was passed positionally to `urllib.request.urlopen` and interpreted as request body data. Fixed by passing `timeout` by keyword.
- The second live schema attempt exposed an OpenAI structured-output schema limitation: top-level `oneOf` is not permitted. The adapter now uses an OpenAI-compatible executable-action schema and normalizes the result back to the local decision contract.
- The third live schema attempt exposed that nullable `reason` was too loose for the local contract. The adapter schema now requires string values and strips action-specific fields before validation.
- The final schema-constrained run produced a valid `defer` decision. Execution correctly made no protocol mutation, and the persisted event log remained the original request event.

Follow-ups:

- Consider whether prompt context should state capacity values more explicitly; the model cited capacity despite active load being `1` and no max capacity included in context.
- Decide whether non-mutating `defer` decisions should eventually append an observation/audit event or remain outside protocol history.

## 2026-09-19: GPT-4o Mini Schema-Constrained Decision With Explicit Capacity

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Scenario: Dev/test inbound request scenario from `seed_inbound_request_scenario`.

Prompt/manual reference: `docs/development/llm-experiment-manual.md`, context package with explicit capacity fields and OpenAI Responses API JSON Schema response format.

Decision context capacity:

```json
{
  "active_load": 1,
  "max_active_negotiations": 5,
  "capacity_remaining": 4
}
```

Validated decision:

```json
{
  "action": "accept_negotiation",
  "negotiation_id": "negotiation_inbound_request",
  "actor_agent_id": "agent_2"
}
```

Validation result: Passed through `parse_llm_decision`; parsed action was `accept_negotiation`.

Execution result: Passed through `execute_decision_against_existing_scenario`; result was mutating: `{"executed": true, "action": "accept_negotiation"}`.

Resulting event history:

```json
[
  {
    "type": "open_negotiation_request",
    "actor_agent_id": "agent_1",
    "negotiation_id": "negotiation_inbound_request"
  },
  {
    "type": "open_negotiation_response",
    "actor_agent_id": "agent_2",
    "negotiation_id": "negotiation_inbound_request",
    "payload": {
      "decision": "accept"
    }
  }
]
```

Observations:

- After explicit capacity fields were added, the same provider/model selected `accept_negotiation` instead of citing capacity as a reason to defer.
- This suggests capacity context materially affects observed model decisions and should remain explicit in future experiments.

Follow-ups:

- Add scenario variants for near-capacity and at-capacity agents to observe whether models defer or reject appropriately.
