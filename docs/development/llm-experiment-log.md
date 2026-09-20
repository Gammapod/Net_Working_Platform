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
