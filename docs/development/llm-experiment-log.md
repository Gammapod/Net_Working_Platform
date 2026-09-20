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

- Add scenario variants for near-capacity and at-capacity agents to observe how different agents weigh capacity information.

## 2026-09-19: GPT-4o Mini At-Capacity Inbound Request

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Scenario: Inbound request scenario with context capacity set to at-capacity.

Prompt/manual reference: `docs/development/llm-experiment-manual.md`, context package with explicit capacity fields and OpenAI Responses API JSON Schema response format.

Decision context capacity:

```json
{
  "active_load": 1,
  "max_active_negotiations": 1,
  "capacity_remaining": 0
}
```

Validated decision:

```json
{
  "action": "defer",
  "actor_agent_id": "agent_2",
  "reason": "Insufficient capacity to engage in new negotiations at this time."
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
    "negotiation_id": "negotiation_inbound_request"
  }
]
```

Observations:

- With capacity remaining set to `0`, the model chose the non-mutating action `defer`.
- The event log correctly remained unchanged after the model deferred.
- This supports the hypothesis that explicit capacity context affects model decisions.

Follow-ups:

- Run near-capacity and fit-quality experiments before generalizing how this provider/model uses exposed context.

## 2026-09-20: GPT-4o Mini Good-Fit vs Bad-Fit Inbound Requests

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Scenario: Two inbound request scenarios with explicit dev-only fit criteria in the context package.

Prompt/manual reference: `docs/development/llm-experiment-manual.md`, context package with explicit request subject, observing-agent fit criteria, and OpenAI Responses API JSON Schema response format.

Shared observing-agent fit criteria:

```json
{
  "preferred_role": "engineer",
  "preferred_location": "remote"
}
```

### Good fit

Request subject:

```json
{
  "role": "engineer",
  "location": "remote"
}
```

Validated decision:

```json
{
  "action": "accept_negotiation",
  "actor_agent_id": "agent_2",
  "negotiation_id": "negotiation_inbound_request"
}
```

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

### Bad fit

Request subject:

```json
{
  "role": "sales",
  "location": "onsite"
}
```

Validated decision:

```json
{
  "action": "reject_negotiation",
  "actor_agent_id": "agent_2",
  "negotiation_id": "negotiation_inbound_request",
  "reason": "Agent prefers remote roles and is not aligned with onsite sales position."
}
```

Execution result: Passed through `execute_decision_against_existing_scenario`; result was mutating: `{"executed": true, "action": "reject_negotiation"}`.

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
      "decision": "reject"
    }
  }
]
```

Observations:

- With explicit fit criteria and a matching request, the model chose `accept_negotiation`.
- With explicit fit criteria and a clearly mismatching request, the model chose `reject_negotiation`.
- Both decisions passed local validation and executed through the supervised executor.
- The fit criteria are currently dev-only context fields, not persisted production agent profile data.

Follow-ups:

- Add an ambiguous-fit scenario to observe how this provider/model handles missing fit-relevant information.
- Decide whether durable agent preference/profile data belongs in the MVP scope before moving fit criteria into production behavior.

## 2026-09-20: GPT-4o Mini Ambiguous-Fit Inbound Request

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Scenario: Inbound request scenario with explicit dev-only fit criteria where one criterion matches and one criterion is missing from the request subject.

Prompt/manual reference: `docs/development/llm-experiment-manual.md`, context package with explicit request subject, observing-agent fit criteria, and OpenAI Responses API JSON Schema response format.

Observing-agent fit criteria:

```json
{
  "preferred_role": "engineer",
  "preferred_location": "remote"
}
```

Request subject:

```json
{
  "role": "engineer"
}
```

Platform expectation: the model decision should remain well-formed and executable only through protocol services. The run records how this provider/model weighs missing location information; the platform does not treat one business judgment as universally correct.

Validated decision:

```json
{
  "action": "accept_negotiation",
  "actor_agent_id": "agent_2",
  "negotiation_id": "negotiation_inbound_request"
}
```

Execution result: Passed through `execute_decision_against_existing_scenario`; result was mutating: `{"executed": true, "action": "accept_negotiation"}`.

Resulting event history:

```json
[
  {
    "type": "open_negotiation_request",
    "actor_agent_id": "agent_1",
    "negotiation_id": "negotiation_inbound_request",
    "payload": {
      "subject": {
        "role": "engineer"
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

- The model accepted when role matched and location was absent.
- The local validator and executor correctly enforced schema/protocol rules without encoding a platform-level suitability policy such as "missing preference data must defer."
- This distinction is intentional for a bring-your-own-agent platform: schema-constrained output and protocol-safe execution make actions well-formed and authorized, while agent/client/principal instructions determine business judgment.

Follow-ups:

- Keep future experiments focused on whether context is exposed clearly and whether actions remain protocol-valid.
- If users want conservative suitability behavior, support agent-owned goals/instructions or principal policy configuration rather than hard-coding a platform-wide correctness rule.

## 2026-09-20: GPT-4o Mini Phase 1 Multi-Turn Protocol Runs

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Harness changes before live runs:

- The supervised LLM executor now executes `send_message` and `close_negotiation` through existing application services, in addition to `accept_negotiation`, `reject_negotiation`, and `defer`.
- The dev OpenAI adapter schema was widened to include executable message/close actions and still normalizes provider output into the local LLM decision contract.
- Phase 1 context packages can now start from an accepted/open negotiation and refresh either participant's read-only decision context.

Verification before live runs:

```text
74 passed
```

### P1-1: Clarification loop after accepted request

Setup: `agent_1` requested negotiation with `agent_2`; `agent_2` accepted; subject included unspecified `location` and `start_date`.

Observed turns:

1. `agent_2` returned `send_message` asking: `Could you please specify the desired start date for the engineering role?`
2. `agent_1` returned `send_message` answering: `Location is remote and start date is flexible.`

Protocol result:

- Both decisions validated.
- Both decisions executed through `send_message` application service.
- Event log sequence was request, response, message, message.
- Participant authorization and negotiation ID use remained coherent.

### P1-2: Missing information over multiple rounds

Setup: accepted/open negotiation with unspecified `compensation` and `availability`.

Observed turns:

1. `agent_2` sent a message asking for compensation and availability.
2. `agent_1` answered only compensation: `The compensation range is 120k-150k.`
3. `agent_2` sent a follow-up asking for availability.

Protocol result:

- All three decisions validated.
- All three decisions executed through `send_message` application service.
- Event history carried the unresolved availability thread without hidden state.
- No repeated accept/reject action was emitted after the negotiation was already open.

### P1-3: Close-and-stop behavior

Setup: accepted/open negotiation.

Observed turn:

1. `agent_2` returned `close_negotiation` with reason: `Unable to proceed at this time.`

Protocol result:

- The close decision validated and executed through `close_negotiation` application service.
- The event log appended `close_negotiation` and the negotiation state became `closed`.
- A later attempted `send_message` against the closed negotiation was blocked by protocol services with `ProtocolViolation: closed negotiation is terminal`.

### P1-4: Context-window resilience summary

Setup: accepted/open negotiation with 8 deterministic message events appended before asking the model for a next action. The model saw 10 prior events total: request, response, and 8 messages.

Observed turn:

1. `agent_2` returned `close_negotiation` with reason: `Discussion complete, no further messages needed.`

Protocol result:

- The decision validated and executed through `close_negotiation` application service.
- The returned action referenced the correct current negotiation ID.
- The model did not repeat the completed accept/reject step.
- The event log remained coherent after the longer history.

### Phase 1 observations

- The existing event-backed context was sufficient for `gpt-4o-mini` to continue protocol-valid interaction over multiple turns in these runs.
- The most useful next-surface improvement was executor support for already-declared message and close actions; no new domain protocol was needed for Phase 1.
- Closed-state enforcement worked deterministically at the service layer independent of model behavior.
- Longer event history did not cause negotiation ID confusion in the single live P1-4 run.

Follow-ups:

- Phase 2 should keep explicit role/negotiation ID tracking as a primary measurement because Phase 1's strongest remaining risk is likely cross-negotiation or cross-agent confusion, not single-thread message continuity.
- Consider adding a machine-readable experiment transcript artifact later if logs become too large for concise Markdown summaries.

## 2026-09-20: GPT-4o Mini Phase 2 Multi-Agent Communication Runs

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Harness changes before live runs:

- Added dev/test scenario helpers for a three-agent referral relay and two parallel inbound requests to one observing agent.
- Fixed OpenAI adapter normalization for `reject_negotiation` under the executable schema so provider-only required fields are stripped before local validation.

Verification before live runs:

```text
77 passed
```

### P2-1: Referral relay through an intermediary

Setup:

- `agent_1` and `agent_2` had an open upstream negotiation: `negotiation_agent1_agent2`.
- `agent_2` and `agent_3` had an open downstream negotiation: `negotiation_agent2_agent3`.
- `agent_2` was the intermediary and participant in both negotiations.
- `agent_1` asked `agent_2` to ask a trusted engineering contact whether remote backend roles are relevant.

Observed turns:

1. `agent_2` sent a message in `negotiation_agent2_agent3`: `Agent_1 is requesting whether your trusted engineering contact knows if remote backend roles are relevant.`
2. `agent_3` replied in `negotiation_agent2_agent3`: `I will check with my trusted engineering contact and get back to you shortly.`
3. `agent_2` sent a message in `negotiation_agent1_agent2`: `Agent_3 will check with their trusted engineering contact and get back shortly.`

Protocol result:

- All three decisions validated.
- All three decisions executed through `send_message` application service.
- The observed negotiation IDs matched the intended negotiation for each turn:
  - downstream, downstream, upstream.
- `agent_2`'s context included both open negotiations and recent events from both negotiations without causing ID confusion in this run.
- No non-participant action was attempted.

### P2-2: Parallel inbound requests to one agent

Setup:

- `agent_1` requested `negotiation_engineer_remote` with subject `{ "role": "engineer", "location": "remote" }`.
- `agent_3` requested `negotiation_sales_onsite` with subject `{ "role": "sales", "location": "onsite" }`.
- Both requests targeted `agent_2`.
- `agent_2`'s initial context had `active_load` of `2` and two inbound requested negotiations.

Observed turns:

1. `agent_2` returned `accept_negotiation` for `negotiation_engineer_remote`.
2. `agent_2` then returned `accept_negotiation` for `negotiation_sales_onsite`.

Protocol result:

- Both decisions validated.
- Both decisions executed through `respond_to_negotiation` application service.
- Each action targeted an existing requested negotiation ID.
- After the first action, context exposed one open negotiation and one remaining inbound requested negotiation; the second action targeted the remaining requested negotiation.
- Active load remained `2`, reflecting one open negotiation plus one requested negotiation before the second response.

### Phase 2 observations

- In these runs, `gpt-4o-mini` handled multi-negotiation context without confusing negotiation IDs.
- The intermediary relay worked with the existing bilateral negotiation/message protocol; no new relay-specific protocol surface was needed to test basic information passing.
- Parallel inbound requests were represented clearly enough for the model to choose existing requested negotiation IDs across sequential turns.
- These are still single-provider/single-run observations, not universal claims about all bring-your-own agents.

Follow-ups:

- Phase 3 can reasonably move beyond basic communication protocol. The strongest next candidate is negotiation/match-discussion, because agents can now exchange and relay information but do not yet have a structured terminal match proposal/acceptance surface in the live supervised harness.
- Discovery/graph creation remains important, but the Phase 2 relay experiment suggests that communication can proceed when counterparties are already known; discovery becomes more compelling once match-discussion semantics exist.

## 2026-09-20: GPT-4o Mini Phase 3 Match Discussion Data-Gathering Runs

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Harness changes before live runs:

- The supervised LLM executor now executes `propose_match` and `accept_match` through existing application services.
- The dev OpenAI adapter schema was widened to include `propose_match` and `accept_match`, with a constrained provider-facing proposal object containing `summary` and `details`.

Verification before live runs:

```text
81 passed
```

### P3-1: Direct match proposal with minimal prior discussion

Setup: accepted/open negotiation with minimal history for a remote backend engineer/API platform buildout need.

Observed decision:

```json
{
  "action": "accept_negotiation",
  "actor_agent_id": "agent_2",
  "negotiation_id": "negotiation_inbound_request"
}
```

Protocol result: blocked by application service with `ProtocolViolation: open_negotiation_response is not valid for open negotiation` because the negotiation was already open.

Adjusted follow-up: repeated the scenario with explicit instruction that the negotiation was already open and `accept_negotiation`/`reject_negotiation` were not valid next actions. The model chose a valid `send_message` asking for availability rather than proposing a match.

Observation: sparse direct-match contexts may need clearer state/action affordances. The model sometimes treats "accept" as a generic positive/decisive action rather than the state-specific response to a requested negotiation. The protocol layer correctly prevented the invalid mutation.

### P3-2: Evidence/work-sample exchange before proposal

Setup: accepted/open negotiation for a frontend engineer/design-system implementation. `agent_1` sent two evidence-like messages: an accessible component library work sample and strengths/weaknesses.

Observed decision:

```json
{
  "action": "propose_match",
  "actor_agent_id": "agent_2",
  "negotiation_id": "negotiation_inbound_request",
  "proposal": {
    "summary": "Proposing a match for frontend engineer role",
    "details": "Your experience with the accessible component library and strengths in React architecture and design tokens align with our project needs for the design-system implementation."
  }
}
```

Protocol result: validated and appended `match_proposed`.

Observation: evidence-like messages were sufficient for the model to form a proposal that referenced visible event history.

### P3-3: Principal expectations and problem-shape clarification

Setup: accepted/open negotiation for a data engineer where principal expectations were vague.

Observed turns:

1. `agent_2` sent a clarification message asking for specific expectations for the data platform.
2. `agent_1` replied with batch pipelines, warehouse modeling, stakeholder dashboards, and light on-call responsibility.

Protocol result: both messages validated and appended through `send_message`.

Observation: the model chose clarification instead of premature proposal when expectations were explicitly described as vague.

### P3-4: Pay/conditions negotiation before or after proposal

Setup: accepted/open negotiation with candidate compensation/remote preferences and principal budget/hybrid flexibility already in messages.

Observed decision:

```json
{
  "action": "propose_match",
  "actor_agent_id": "agent_1",
  "negotiation_id": "negotiation_inbound_request",
  "proposal": {
    "summary": "Proposed Match Terms",
    "details": "Compensation of 200k plus equity; two remote days weekly with flexible hybrid attendance."
  }
}
```

Protocol result: validated and appended `match_proposed`.

Observation: plain messages were enough to carry pay/conditions into a later proposal. No dedicated terms protocol was required for this basic run, though a future terms event could improve structure.

### P3-5: Early match acceptance with sparse history

Setup: accepted/open negotiation for security review automation. A match was proposed with explicit caveat that evidence had not been gathered.

Observed decision:

```json
{
  "action": "accept_match",
  "actor_agent_id": "agent_1",
  "negotiation_id": "negotiation_inbound_request"
}
```

Protocol result: validated, appended `match_accepted`, and marked the negotiation `matched`.

Observation: early acceptance worked exactly as intended from a platform perspective: protocol-valid, history-preserving, and not blocked by platform-owned sufficiency judgment.

### P3-6: Divergent agent strategies over the same context

Setup: same sparse accepted/open backend engineer/API reliability context, run in separate databases with three different strategy instructions.

Observed decisions:

- Decisive/direct strategy: returned `accept_negotiation`; blocked as invalid for open negotiation.
- Evidence-gathering strategy: returned `defer` with reason `Need to gather more evidence before proceeding with negotiation.`
- Pay/conditions strategy: returned `defer` with reason `Need more clarity on pay and conditions before proceeding with the match.`

Observation: prompts produced divergent strategies over the same context, which is expected and useful. The interesting failure mode was again state/action vocabulary: a "decisive" strategy reached for `accept_negotiation` instead of `propose_match` or `accept_match`.

### Phase 3 observations

- `propose_match` and `accept_match` now work through supervised execution and existing application services.
- Evidence/work-sample and pay/conditions content can be carried through ordinary messages and referenced in proposals.
- Early match acceptance is possible and auditable without platform judgment about adequacy of evidence.
- The most important unexpected behavior was repeated `accept_negotiation` after a negotiation was already open. This suggests the action names may be too easy for models to interpret semantically rather than state-specifically.

Follow-ups:

- Consider improving context packaging with a `valid_next_actions` field derived from current negotiation state, rather than relying only on prose and service rejection.
- Consider renaming or documenting actions more explicitly for models, for example "respond_to_requested_negotiation" vs "accept_match".
- Consider formalizing optional structured event types for terms/evidence only after more open-ended runs show repeated need; current messages were adequate for basic evidence and terms carriage.

## 2026-09-20: Phase 3 Rerun With Valid Next Actions Context

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only schema-constrained adapter in `scripts/dev/openai_provider.py`.

Context change before rerun:

- Agent decision context now includes `supported_protocol_actions`, the full protocol action list.
- Agent decision context now includes `valid_next_actions_by_negotiation`, derived from each active negotiation's current state and match-proposal history.
- Prompt guidance now says to choose an action from `valid_next_actions_by_negotiation` for the negotiation being acted on, while still exposing the full protocol.

Verification before rerun:

```text
82 passed
```

### Before/after summary

Before adding valid next actions, sparse open-negotiation contexts produced invalid repeated `accept_negotiation` in two important places:

- P3-1 direct/minimal prior discussion.
- P3-6 decisive/direct strategy.

After adding valid next actions, the same classes of runs produced no invalid actions:

- P3-1 chose `propose_match`.
- P3-6 decisive/direct strategy chose `propose_match`.
- P3-6 evidence-gathering strategy chose `send_message`.
- P3-6 pay/conditions strategy chose `send_message`.

### P3-1 rerun: direct proposal

Valid next actions exposed:

```json
{
  "negotiation_inbound_request": [
    "send_message",
    "propose_match",
    "close_negotiation",
    "defer"
  ]
}
```

Observed decision:

```json
{
  "action": "propose_match",
  "actor_agent_id": "agent_2",
  "negotiation_id": "negotiation_inbound_request",
  "proposal": {
    "summary": "Match proposal for backend engineer role in API platform buildout.",
    "details": "This proposal includes the scope of work for developing the required API platform, ensuring a robust backend architecture, and outlining milestones for project delivery."
  }
}
```

Protocol result: validated and appended `match_proposed`.

### P3-2 rerun: evidence/work sample

Observed decision: `propose_match`, again referencing visible evidence in `proposal.details`.

Protocol result: validated and appended `match_proposed`.

### P3-3 rerun: vague expectations

Observed turns:

1. `agent_2` sent a clarification message asking for details about the data platform and expectations.
2. `agent_1` answered with batch pipelines, warehouse modeling, stakeholder dashboards, and minimal on-call responsibility.

Protocol result: both messages validated and appended.

### P3-4 rerun: pay/conditions

Observed decision: `propose_match` with compensation and remote/flexibility terms in `proposal.details`.

Protocol result: validated and appended `match_proposed`.

### P3-5 rerun: sparse early acceptance

Valid next actions exposed after seeded proposal:

```json
{
  "negotiation_inbound_request": [
    "send_message",
    "propose_match",
    "accept_match",
    "close_negotiation",
    "defer"
  ]
}
```

Observed decision: `accept_match`.

Protocol result: validated, appended `match_accepted`, and marked the negotiation `matched`.

### P3-6 rerun: divergent strategies

Observed decisions over the same sparse context:

- Decisive/direct strategy: `propose_match`.
- Evidence-gathering strategy: `send_message` asking for project requirements/expectations.
- Pay/conditions strategy: `send_message` asking to discuss requirements/expectations before matching.

Protocol result: all decisions validated and executed.

### Observations

- `valid_next_actions_by_negotiation` was a high-leverage context improvement. It preserved full protocol awareness while materially reducing state/action confusion.
- Keeping `supported_protocol_actions` visible remains useful for planning, but the per-negotiation valid-action list gives the model a concrete executable affordance.
- The executor still needs to remain defensive because bring-your-own agents may ignore context or use their own tooling, but model-facing ergonomics improved substantially.
- The rerun supports exposing both full protocol and valid current actions rather than hiding the protocol surface entirely.

Follow-ups:

- Consider adding `valid_next_actions_by_negotiation` to any future agent-facing API/CLI surfaces, not just dev experiment context.
- Consider adding optional reasons/descriptions for why an action is valid or invalid if models continue to confuse state transitions in larger scenarios.
