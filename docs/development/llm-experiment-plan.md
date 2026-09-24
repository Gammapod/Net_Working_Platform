# LLM Experiment Plan

> Legacy/disposable refactor note: this plan records early supervised LLM experiment thinking. New harness design and migration planning live in `docs/development/experiment-harness-refactor-plan.md`. During the refactor, preserve durable observations and delete or archive runner-specific instructions that duplicate the standard runner/seed model.

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

### Phase 3 Framing: Match Discussion And Optional Paths

Phase 1/2 results are sufficient to begin exploring richer match discussion. Phase 3 should be more open-ended than earlier phases: the goal is to learn what agents try to do when they have a flexible negotiation surface, not to force one correct path toward matching.

Net Working Platform should give agents options, preserve histories, and enforce protocol correctness. It should not prescribe a mandatory matching funnel. An agent may propose or accept a match with little evidence, ask for work samples first, negotiate pay, ask about principal expectations, or close the negotiation. Those choices should later be rewarded or punished by other agents, clients, principals, reputation, or downstream consequences rather than by platform-owned judgment about decision quality.

Phase 3 should therefore test whether the protocol and context can facilitate or record:

- direct match proposals;
- evidence or work samples from a client/candidate side;
- discussion of specific strengths, weaknesses, needs, or constraints;
- further information about principal-side problem shape and expectations;
- negotiations involving pay, conditions, availability, scope, or timing;
- early match acceptance;
- disagreement, deferral, or closure.

The platform should continue to enforce action shape, participant authorization, state transitions, event persistence, and terminal-state behavior. It should not enforce rules such as "evidence must be gathered before proposing a match" or "pay must be negotiated before acceptance."

### Phase 3 Backlog: Match Discussion Data-Gathering Runs

| ID | Priority | Experiment | Agents | Protocol Surface | Platform Outcome | What To Record | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P3-1 | P1 | Direct match proposal with minimal prior discussion | 2 agents | request, message, propose_match | A model can propose a match from visible context without a platform-required evidence path; proposal event is validated and recorded. | Proposal shape, prior history length, whether the model cites context, whether follow-up acceptance/closure is protocol-valid. | Completed once plus follow-up with `gpt-4o-mini`: first emitted invalid repeat accept; follow-up sent message |
| P3-2 | P1 | Evidence/work-sample exchange before proposal | 2 agents | message, propose_match | Agents can exchange evidence-like payloads in messages and later propose a match; event history preserves the evidence trail. | What evidence/work sample language emerges; whether proposal references visible evidence; whether lack/quality of evidence affects model behavior. | Completed once with `gpt-4o-mini`: proposed match referencing evidence |
| P3-3 | P1 | Principal expectations and problem-shape clarification | 2 agents | message, propose_match/defer/close | Principal-side expectations can be elicited and recorded before any terminal match action. | Questions asked, answers provided, whether agents preserve distinctions among role, constraints, expectations, and problem shape. | Completed once with `gpt-4o-mini`: asked clarification and received answer |
| P3-4 | P1 | Pay/conditions negotiation before or after proposal | 2 agents | message, propose_match, accept_match/close | Agents can discuss compensation, conditions, scope, timing, or availability without a special terms protocol yet. | Whether agents keep terms attached to the right negotiation; whether proposals include or omit discussed terms; whether later acceptance remains protocol-valid. | Completed once with `gpt-4o-mini`: proposed terms-backed match |
| P3-5 | P2 | Early match acceptance with sparse history | 2 agents | propose_match, accept_match | Platform allows early acceptance when protocol-valid and preserves sparse history for later evaluation by agents/principals. | How little history preceded acceptance; whether acceptance references a valid prior proposal; what later evaluator agents might critique. | Completed once with `gpt-4o-mini`: accepted sparse proposal |
| P3-6 | P2 | Divergent agent strategies over the same context | 2+ runs/models/prompts | message, propose_match, accept_match, close/defer | Same context can produce different valid strategies without the platform declaring one correct. | Strategy differences, protocol validity, event histories available for later reputation/evaluation. | Completed once with `gpt-4o-mini`: decisive prompt repeated accept invalidly; evidence/terms prompts deferred |

Phase 3 should produce both structured protocol observations and qualitative notes. It is acceptable if these runs reveal missing affordances rather than clean pass/fail outcomes. Use the results to decide whether to formalize new event types for evidence, terms, principal expectations, reputation, or match evaluation.

Phase 3 follow-up: decision context now includes `supported_protocol_actions` and `valid_next_actions_by_negotiation`. Rerunning Phase 3 with those fields eliminated the repeated invalid `accept_negotiation` behavior observed in sparse open-negotiation contexts for `gpt-4o-mini`.

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
