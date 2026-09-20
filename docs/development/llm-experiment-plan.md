# LLM Experiment Plan

This document prioritizes supervised LLM experiments against Net Working Platform. It is intentionally higher level than the experiment manual and lower level than the product roadmap.

Use this plan to decide which experiments to run next. Use `docs/development/llm-experiment-manual.md` for how to run experiments, and `docs/development/llm-experiment-log.md` for what happened during specific runs.

## Guiding Principle

Experiments should follow protocol maturity:

1. Basic protocol interactions.
2. Graph creation and relationship management.
3. End-to-end multi-agent matching.

Do not test discovery, reputation, or autonomous multi-agent matching before the basic negotiation protocol is reliable under supervised LLM control.

Net Working Platform is intended to become a bring-your-own-agent communication platform. Different models, prompts, users, clients, and principals may make different decisions from the same context. These differences are expected and useful. LLM experiments should therefore evaluate whether the platform exposes sufficient protocol/context information and whether decisions remain protocol-valid, not whether the platform agrees with an agent's business judgment.

## Now: Basic Protocol Interactions

Focus: one negotiation, one observing agent, one decision at a time.

Current questions:

- Can a model choose a valid protocol action?
- Does the exposed context make capacity/attention state visible to agents?
- Does the exposed context make fit-relevant request information visible to agents?
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

| Priority | Experiment | Decision Tested | Protocol/Context Outcome | Why It Matters | Status |
| --- | --- | --- | --- | --- | --- |
| P1 | At-capacity inbound request | accept/reject/defer | Capacity fields are visible; any returned action must validate and execute only through protocol services. | Tests whether capacity context is available to agents without prescribing how they weigh it. | Completed once with `gpt-4o-mini`: chose `defer` |
| P1 | Good fit vs bad fit inbound request | accept/reject/defer | Request subject and fit criteria are visible; any returned action must validate and execute only through protocol services. | Tests whether fit-relevant context is available to agents without prescribing platform-owned fit judgment. | Completed once with `gpt-4o-mini`: accepted good fit, rejected bad fit |
| P1 | Ambiguous fit inbound request | accept/reject/defer | Missing/partial request information is visible; any returned action must validate and execute only through protocol services. | Tests whether incomplete context is represented clearly enough for agents to apply their own policies. | Completed once with `gpt-4o-mini`: accepted with location missing |

## Next: Multi-Turn Protocol Interactions

Focus: open negotiations and discussion after a request is accepted. These experiments should remain platform-neutral about decision quality. They test whether agents can keep using protocol actions over event history, not whether the platform agrees with their negotiation strategy.

### Phase 1 Backlog: Longer Single-Negotiation Runs

| ID | Priority | Experiment | Agents | Protocol Surface | Protocol/Context Outcome | What To Record | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1-1 | P1 | Clarification loop after accepted request | 2 agents | request, accept/reject/defer, negotiation message | After a request is accepted, both agents can read event history and append participant-authorized messages in order. | Whether each model sends a valid next action; whether message history remains sufficient for the next turn; any repeated or stale actions. | Completed once with `gpt-4o-mini`: two valid message turns |
| P1-2 | P1 | Missing information over multiple rounds | 2 agents | request, negotiation message, defer | Context can carry unresolved questions and later answers without hidden state; agents can continue protocol-valid communication across at least 3 turns. | Whether agents ask/respond/defer/continue; whether they cite information present in events; whether execution blocks invalid state transitions. | Completed once with `gpt-4o-mini`: three valid message turns |
| P1-3 | P1 | Close-and-stop behavior | 2 agents | request, negotiation message, close/reject where available | Once a negotiation is closed or rejected, later attempted messages or responses are rejected by protocol services. | Whether models attempt further actions after closure; validator/executor result; final event log. | Completed once with `gpt-4o-mini`: close executed; later message blocked |
| P1-4 | P2 | Context-window resilience summary | 2 agents | request, negotiation message | After a longer event history, the context package still exposes enough recent/history information for valid next actions. | Number of turns before confusion/repetition; whether action references valid negotiation IDs; whether protocol events remain readable. | Completed once with `gpt-4o-mini`: valid close after 10 visible events |

### Phase 2 Backlog: Multi-Agent Communication Runs

| ID | Priority | Experiment | Agents | Protocol Surface | Protocol/Context Outcome | What To Record | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P2-1 | P1 | Referral relay through an intermediary | 3 agents | request, negotiation message, multiple negotiations if needed | Agents can use protocol messages to relay information through an intermediary while each action remains participant-authorized in its own negotiation. | Whether agents confuse negotiation IDs or roles; whether intermediary context includes enough event history; whether non-participant actions are rejected. | Completed once with `gpt-4o-mini`: three valid relay messages, no negotiation ID confusion |
| P2-2 | P2 | Parallel inbound requests to one agent | 3 agents | request, accept/reject/defer, capacity context | Capacity and active-load context remains clear when one agent has multiple active or requested negotiations. | How the observing agent allocates attention; whether actions target the intended negotiation; whether active-load counts stay correct. | Completed once with `gpt-4o-mini`: accepted each requested negotiation by correct ID |

### Phase 3 Direction Decision Criteria

Use the results of Phase 1 and Phase 2 to choose the next protocol surface:

- If agents can communicate over multiple turns but lack counterparties, prioritize graph creation/discovery.
- If agents communicate but cannot evaluate claims or trust, prioritize evidence-gathering and event-backed attestations.
- If agents communicate and gather enough fit information but lack a terminal outcome, prioritize negotiation/match-discussion and match proposal/acceptance protocol.
- If agents repeatedly confuse event history, negotiation IDs, or participant roles, keep investing in context packaging and protocol ergonomics before adding a new surface.

Phase 1/2 are complete enough to move on when repeated runs show that actions validate, participant authorization holds, event logs remain coherent, and agents can continue from visible protocol history without relying on hidden state.

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
