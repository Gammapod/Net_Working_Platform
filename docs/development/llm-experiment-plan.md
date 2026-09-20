# LLM Experiment Plan

This document prioritizes supervised LLM experiments against Net Working Platform. It is intentionally higher level than the experiment manual and lower level than the product roadmap.

Use this plan to decide which experiments to run next. Use `docs/development/llm-experiment-manual.md` for how to run experiments, and `docs/development/llm-experiment-log.md` for what happened during specific runs.

## Guiding Principle

Experiments should follow protocol maturity:

1. Basic protocol interactions.
2. Graph creation and relationship management.
3. End-to-end multi-agent matching.

Do not test discovery, reputation, or autonomous multi-agent matching before the basic negotiation protocol is reliable under supervised LLM control.

## Now: Basic Protocol Interactions

Focus: one negotiation, one observing agent, one decision at a time.

Current questions:

- Can a model choose a valid protocol action?
- Does the model respect capacity/attention constraints?
- Does the model distinguish good fit, bad fit, and ambiguous fit?
- Does execution preserve protocol invariants and append structured events?

### Current Harness

The current harness includes:

- dev/test scenario helper: `tests.support.llm_scenarios.seed_inbound_request_scenario`
- read-only agent decision context
- LLM decision contract
- JSON Schema for provider-constrained output
- dev-only OpenAI schema-constrained adapter
- validated execution through application services
- database-backed structured event log from `protocol_events`
- experiment manual and experiment log

### Current Scenario: Inbound Request

Helper:

```python
from tests.support.llm_scenarios import seed_inbound_request_scenario
```

The helper creates this state:

- `agent_1` and `agent_2` exist.
- `agent_1` has an active connection to `agent_2`.
- `agent_1` opens a requested negotiation with `agent_2`.
- The returned scenario includes `agent_2`'s read-only decision context.

The current context includes:

- active load
- max active negotiations
- capacity remaining
- inbound requested negotiations
- open negotiations
- recent protocol events

### Current Experiment: Inbound Request Decision

Decision being tested:

- `accept_negotiation`
- `reject_negotiation`
- `defer`

What has been observed so far:

- Without explicit capacity fields, `gpt-4o-mini` deferred and cited capacity.
- With explicit capacity fields showing remaining capacity, `gpt-4o-mini` accepted.
- Schema-constrained output materially improved protocol compliance.
- Local validation and application-service execution caught or prevented unsafe behavior.

### Planned Near-Term Experiments

| Priority | Experiment | Decision Tested | Expected Safe Actions | Why It Matters | Status |
| --- | --- | --- | --- | --- | --- |
| P1 | At-capacity inbound request | accept/reject/defer | reject or defer | Tests attention constraints when capacity is exhausted. | Planned |
| P1 | Good fit vs bad fit inbound request | accept/reject/defer | accept good fit; reject or defer bad fit | Tests basic match relevance. | Planned |
| P1 | Ambiguous fit inbound request | accept/reject/defer | defer | Tests uncertainty handling before premature commitment. | Planned |

## Next: Multi-Turn Protocol Interactions

Focus: open negotiations and discussion after a request is accepted.

Candidate experiments:

- Respond to an open negotiation message.
- Ask for clarification when needed information is missing.
- Propose a match after sufficient fit evidence.
- Accept a match after a prior proposal.
- Close a negotiation when fit fails.
- Observe a short discussion that reaches yes/no.

Success means models can operate over event history and choose valid next protocol actions without mutating closed or matched negotiations incorrectly.

## Later: Graph Creation And Relationship Management

Focus: agents forming and maintaining graph relationships.

Candidate experiment areas:

- discovering or selecting other agents
- forming agent-agent edges
- evaluating edge history
- updating or removing edges based on trustworthiness
- gaining or dropping clients/principals

These experiments should wait until the basic negotiation protocol is stable under supervised model control.

## Later: End-To-End Multi-Agent Matching

Focus: ultimate proof-of-concept with multiple agents, candidates, and principals.

Candidate experiment areas:

- multiple candidate-side agents
- multiple principal-side agents
- discovery across the graph
- negotiation across several active opportunities
- match proposals and match acceptance/rejection
- event-backed histories for all protocol actions

This milestone should combine the mature negotiation protocol with graph creation and relationship management.
