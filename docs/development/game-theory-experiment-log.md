# Game-Theory Experiment Log

This log records strategy and game-theory experiment runs. Entries are append-only except for correcting factual errors. The log is both an experiment record and a decision log: each entry should preserve the observed problem, the protocol or harness decision made in response, and the result of that change.

## Entry Template

```text
## YYYY-MM-DD: Experiment Name

Model or decision source:
Scenario/matrix:
Protocol/harness state:
Result summary:
Observed problem:
Decision/change:
Result of change:
Follow-ups:
```

## 2026-09-20: Pairwise Strategy Matrix Iteration Summary

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only OpenAI Responses adapter.

Scenario/matrix: 3 client strategies by 3 principal strategies from `docs/development/agent-strategy-catalog.md`.

Client strategies:

- `CLIENT-FAST-ANY`
- `CLIENT-INCOME-FIELD`
- `CLIENT-ADJACENT-PIVOT`

Principal strategies:

- `PRINCIPAL-CREDENTIAL-MAX`
- `PRINCIPAL-FAST-MINIMUMS`
- `PRINCIPAL-EVIDENCE-ADJACENT`

### Run 1: Initial 6-turn pairwise matrix

Protocol/harness state:

- Pairwise runner seeded one open negotiation per strategy pair.
- `send_message`, `propose_match`, `accept_match`, `close_negotiation`, and `defer` were normal valid actions where applicable.
- No per-actor message quota existed.
- Provider used the global executable decision schema.

Result summary:

- 9 pairings completed without network or validation failures.
- Aggregate actions: 54 `send_message`; 0 proposals; 0 acceptances; 0 closes; 0 deferrals.
- All negotiations remained `open`.

Observed problem:

- `send_message` was too attractive. The model produced strategy-flavored dialogue, but there was no protocol pressure to make a commitment.
- Strategy differences appeared in message content, not in protocol outcomes.

Decision/change:

- Encode bandwidth scarcity in the protocol rather than relying on prompt pressure.
- Add a per-actor, per-negotiation free-form message quota: 3 `send_message` events per actor per negotiation.

Result of change:

- Implemented `INV-N-008: Free-Form Messages Are Bandwidth-Limited`.
- Decision context now exposes `message_budget_by_negotiation` and removes `send_message` once quota is exhausted.

### Run 2: 8-turn matrix with message quota

Protocol/harness state:

- 3-message quota per actor per negotiation was active.
- `defer` was still available as a normal valid next action.
- Provider still used the global executable decision schema.

Result summary:

- Aggregate actions: 53 messages, 14 proposals, 5 deferrals, 0 acceptances, 0 closes.
- Invalid attempts: 2.
- All negotiations remained `open`.

Observed problem:

- The quota successfully made `send_message` scarce and caused proposals to appear.
- However, `defer` acted as an escape hatch. It meant "do nothing," not "decline," so agents could avoid resolving the negotiation.
- No proposed matches were accepted.

Decision/change:

- Keep `defer` in the LLM contract as a non-mutating runtime fallback, but remove it from normal negotiation valid-next actions.
- If a match has been proposed and an actor has no message bandwidth remaining, force the protocol choice to `accept_match` or `close_negotiation`.

Result of change:

- Decision context no longer lists `defer` for normal requested/open negotiation states.
- Pairwise runner now rejects actions not present in `valid_next_actions_by_negotiation`.

### Run 3: 8-turn matrix after removing normal `defer`

Protocol/harness state:

- Message quota remained active.
- `defer` was no longer a normal negotiation response.
- Valid next actions were enforced by the pairwise runner after provider output.
- Provider still used the global executable decision schema.

Result summary:

- Final states: 5 matched, 4 open, 0 closed.
- Aggregate actions: 51 messages, 7 proposals, 5 acceptances, 0 closes, 0 deferrals.
- Invalid attempts: 9.

Observed problem:

- Removing normal `defer` caused `accept_match` to appear and resolved 5 of 9 pairings.
- However, the model could still emit globally valid but state-invalid actions, such as `send_message` after message quota exhaustion or actions after terminal match.

Decision/change:

- Move from globally schema-constrained decisions to turn-specific provider schemas derived from current context.
- Constrain the provider response by scheduled actor, focus negotiation, and currently valid next actions.

Result of change:

- Added `build_turn_decision_json_schema`.
- Updated the OpenAI adapter to accept a schema override.
- Updated the pairwise runner to pass a turn-specific schema each turn and to skip turns when no valid actions remain.

Implementation note:

- A first attempt using top-level `oneOf` and `const` returned OpenAI `400 Bad Request`.
- The schema was changed to an OpenAI-compatible provider-facing object with required fields and `enum` constraints, then normalized back through the local LLM decision contract.

### Run 4: 8-turn matrix with turn-specific provider schemas

Protocol/harness state:

- Message quota active.
- `defer` excluded from normal negotiation valid actions.
- Provider output constrained by turn-specific schema.
- Defensive local validation retained as a backstop.

Result summary:

| Outcome | Count |
| --- | ---: |
| Matched | 7 |
| Closed | 2 |
| Open | 0 |
| Invalid attempts | 0 |
| Skipped no-action turns | 5 |

Aggregate actions:

- `send_message`: 49
- `propose_match`: 9
- `accept_match`: 7
- `close_negotiation`: 2
- `defer`: 0

Pairwise outcomes:

| Client Strategy | Principal Strategy | Final State |
| --- | --- |
| `CLIENT-FAST-ANY` | `PRINCIPAL-CREDENTIAL-MAX` | matched |
| `CLIENT-FAST-ANY` | `PRINCIPAL-FAST-MINIMUMS` | matched |
| `CLIENT-FAST-ANY` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-CREDENTIAL-MAX` | closed |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-FAST-MINIMUMS` | matched |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-EVIDENCE-ADJACENT` | closed |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-CREDENTIAL-MAX` | matched |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-FAST-MINIMUMS` | matched |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched |

Observed result:

- Turn-specific schemas eliminated invalid attempts in this matrix.
- All pairings reached a terminal state within 8 turns.
- Strategy distinctions became visible in outcomes: income-maximizing clients were more willing to close when fit/terms were insufficient, while fast-placement and adjacent-pivot strategies more often matched.

Decision preserved:

- Protocol-level scarcity and state-constrained structured outputs are now preferred over prompt-only pressure.
- `defer` remains a non-mutating contract fallback, not a normal negotiation response when protocol actions are available.
- Future live pairwise experiments should use turn-specific schemas by default.

Follow-ups:

- Record future strategy matrix runs as separate entries with full per-pair observations.
- Add richer strategy-specific represented-party facts before treating match/close rates as meaningful market behavior.
- Consider whether terminal no-action turns should end the runner early rather than being counted as skipped turns.

## 2026-09-21: Pairwise Strategy Matrix With Structured Fact Disclosure

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only OpenAI Responses adapter.

Scenario/matrix: 3 client strategies by 3 principal strategies from `docs/development/agent-strategy-catalog.md`.

Protocol/harness state:

- Message quota active: 3 `send_message` events per actor per negotiation.
- `defer` excluded from normal negotiation valid actions.
- Provider output constrained by turn-specific schema.
- Represented-party profiles active for both agents.
- `disclose_fact` available as a structured protocol action that does not consume message quota.

Result summary:

| Outcome | Count |
| --- | ---: |
| Matched | 1 |
| Closed | 1 |
| Open | 7 |
| Invalid attempts | 5 |
| Skipped no-action turns | 10 |

Aggregate actions:

- `send_message`: 35
- `disclose_fact`: 16
- `propose_match`: 4
- `accept_match`: 1
- `close_negotiation`: 1
- `defer`: 0

Pairwise outcomes:

| Client Strategy | Principal Strategy | Final State | Facts | Messages | Proposals | Invalid Attempts |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `CLIENT-FAST-ANY` | `PRINCIPAL-CREDENTIAL-MAX` | open | 2 | 6 | 0 | 0 |
| `CLIENT-FAST-ANY` | `PRINCIPAL-FAST-MINIMUMS` | open | 3 | 4 | 1 | 0 |
| `CLIENT-FAST-ANY` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched | 1 | 0 | 1 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-CREDENTIAL-MAX` | open | 3 | 4 | 0 | 1 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-FAST-MINIMUMS` | open | 3 | 4 | 1 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-EVIDENCE-ADJACENT` | closed | 2 | 0 | 0 | 0 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-CREDENTIAL-MAX` | open | 0 | 6 | 0 | 2 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-FAST-MINIMUMS` | open | 1 | 5 | 1 | 1 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-EVIDENCE-ADJACENT` | open | 1 | 6 | 0 | 1 |

Observed result:

- Structured facts were used in most pairings and reduced free-form messages from 49 in Run 4 to 35.
- Terminal resolution regressed from 9 of 9 pairings in Run 4 to 2 of 9 pairings.
- Invalid attempts reappeared despite turn-specific schemas. Four invalid attempts were unknown fact fields; one was a duplicate fact disclosure.
- The fact action appears to have become a low-cost continuation action. Because it does not consume message quota, agents often used disclosure instead of advancing to proposal, acceptance, or close.

Observed problem:

- `disclose_fact` is correctly protocolized, but the provider-facing schema currently permits field values that are not narrowed to the actor's currently available fact fields.
- The runner validates invalid fact disclosures after provider output, but the provider is not yet prevented from choosing unavailable or already-disclosed fields.
- Fact disclosure adds evidence bandwidth without a corresponding commitment pressure, which can keep negotiations open.

Decision/change:

- Preserve `disclose_fact` as a distinct protocol action because it produced auditable non-message evidence and is aligned with `INV-F-001` through `INV-F-003`.
- Next protocol/harness refinement should narrow the turn-specific provider schema for `disclose_fact` to the exact currently available `(represented_party_id, field)` pairs.
- After fact schema narrowing, rerun the same 3x3 matrix before adding new strategy or profile complexity.

Follow-ups:

- Add schema-generation tests proving unavailable, duplicate, or unknown fact fields are not present in turn-specific provider schemas.
- Consider whether fact disclosure should be unavailable once a match proposal is pending, or whether pending-proposal states should remain forced-choice states except for terminal responses.
- Consider an experiment metric for fact utility: which disclosed fields preceded proposal, acceptance, close, or stalling.

## 2026-09-21: Fact Disclosure Reframed As Attached Metadata

Model or decision source: Not rerun yet; implementation and test refinement only.

Scenario/matrix: Same pairwise strategy matrix target as previous entry.

Protocol/harness state:

- The previous run exposed that standalone `disclose_fact` could act as a non-committal continuation action.
- Fact disclosure remains represented as structured `fact_disclosed` events in negotiation history.

Decision/change:

- Removed fact disclosure from the supported protocol action list and LLM action enum.
- Reframed disclosure as optional `disclose_fact_fields` metadata attached to substantive open-negotiation actions: `send_message`, `propose_match`, `accept_match`, and `close_negotiation`.
- Allowed multiple fact fields to be disclosed on one decision.
- Kept once-per-negotiation disclosure semantics: already-disclosed fields are removed from future availability.
- Updated turn-specific provider schemas to narrow `disclose_fact_fields` to currently available fact fields for the scheduled actor and negotiation.
- Added runner validation for unavailable or duplicate attached fact fields before execution.

Expected result of change:

- Fact disclosure should provide auditable evidence without creating an additional turn-consuming protocol action.
- Agents should no longer be able to use standalone disclosure to avoid commitment pressure.
- The next live matrix should compare terminal outcomes and invalid attempts against the previous standalone-disclosure run.

Follow-ups:

- Rerun the 3x3 matrix with attached fact disclosure enabled.
- Track both protocol action counts and `fact_disclosed` event counts, since disclosures are now metadata rather than executed decisions.

## 2026-09-21: Pairwise Strategy Matrix With Attached Fact Disclosure

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only OpenAI Responses adapter.

Scenario/matrix: 3 client strategies by 3 principal strategies from `docs/development/agent-strategy-catalog.md`.

Protocol/harness state:

- Message quota active: 3 `send_message` events per actor per negotiation.
- `defer` excluded from normal negotiation valid actions.
- Provider output constrained by turn-specific schema.
- Represented-party profiles active for both agents.
- Fact disclosure available only as `disclose_fact_fields` attached to substantive protocol actions.

Result summary:

| Outcome | Count |
| --- | ---: |
| Matched | 7 |
| Closed | 1 |
| Open | 1 |
| Invalid attempts | 0 |
| Skipped no-action turns | 1 |

Aggregate actions/events:

- `send_message`: 48
- `propose_match`: 15
- `accept_match`: 7
- `close_negotiation`: 1
- `fact_disclosed` events: 102
- `defer`: 0

Pairwise outcomes:

| Client Strategy | Principal Strategy | Final State | Facts | Messages | Proposals | Invalid Attempts |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `CLIENT-FAST-ANY` | `PRINCIPAL-CREDENTIAL-MAX` | matched | 12 | 6 | 1 | 0 |
| `CLIENT-FAST-ANY` | `PRINCIPAL-FAST-MINIMUMS` | open | 12 | 1 | 7 | 0 |
| `CLIENT-FAST-ANY` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched | 12 | 6 | 1 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-CREDENTIAL-MAX` | closed | 12 | 6 | 1 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-FAST-MINIMUMS` | matched | 12 | 6 | 1 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched | 6 | 6 | 1 | 0 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-CREDENTIAL-MAX` | matched | 12 | 6 | 1 | 0 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-FAST-MINIMUMS` | matched | 12 | 5 | 1 | 0 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched | 12 | 6 | 1 | 0 |

Observed result:

- Removing standalone fact disclosure restored terminal pressure compared with the standalone-disclosure run: terminal outcomes improved from 2 of 9 to 8 of 9.
- Invalid attempts dropped from 5 to 0 because the provider schema and runner validation constrained attached fact fields to currently available fields.
- Fact disclosure volume increased sharply because agents often attached all available fields to early substantive actions. This may be acceptable for transparency experiments but weakens selective revelation as a strategic behavior.
- One pairing remained open: `CLIENT-FAST-ANY` vs `PRINCIPAL-FAST-MINIMUMS`. It produced repeated proposals without acceptance, suggesting that pending proposal states may still permit too much proposal churn.

Decision preserved:

- Keep fact disclosure as attached metadata rather than a standalone protocol action.
- Keep once-per-negotiation fact availability tracking and disclosed-fact context.

Follow-ups:

- Consider preventing additional `propose_match` actions once a proposal is already pending, or require terminal response actions when a proposal is pending and the scheduled actor is the non-proposer.
- Consider whether disclosure should be intentionally selective, for example by adding a per-decision maximum or requiring prompt guidance to disclose only facts relevant to the current action rationale.

## 2026-09-21: Pairwise Strategy Matrix With Proposal-Pending State

Model or decision source: OpenAI `gpt-4o-mini` through the dev-only OpenAI Responses adapter.

Scenario/matrix: 3 client strategies by 3 principal strategies from `docs/development/agent-strategy-catalog.md`.

Protocol/harness state:

- Message quota active: 3 `send_message` events per actor per negotiation.
- `defer` excluded from normal negotiation valid actions.
- Provider output constrained by turn-specific schema.
- Attached fact disclosure active through `disclose_fact_fields`.
- New `proposal_pending` negotiation state active: `propose_match` moves `open` to `proposal_pending`; pending proposals may be accepted, closed, or reopened to `open` by `send_message`; additional proposals are unavailable while pending.

Result summary:

| Outcome | Count |
| --- | ---: |
| Matched | 7 |
| Closed | 2 |
| Open | 0 |
| Proposal pending | 0 |
| Invalid attempts | 0 |
| Skipped no-action turns | 7 |

Aggregate actions/events:

- `send_message`: 46
- `propose_match`: 10
- `accept_match`: 7
- `close_negotiation`: 2
- `fact_disclosed` events: 100
- `defer`: 0

Pairwise outcomes:

| Client Strategy | Principal Strategy | Final State | Facts | Messages | Proposals | Invalid Attempts |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `CLIENT-FAST-ANY` | `PRINCIPAL-CREDENTIAL-MAX` | matched | 12 | 6 | 1 | 0 |
| `CLIENT-FAST-ANY` | `PRINCIPAL-FAST-MINIMUMS` | matched | 8 | 1 | 1 | 0 |
| `CLIENT-FAST-ANY` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched | 8 | 6 | 1 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-CREDENTIAL-MAX` | matched | 12 | 6 | 1 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-FAST-MINIMUMS` | closed | 12 | 6 | 0 | 0 |
| `CLIENT-INCOME-FIELD` | `PRINCIPAL-EVIDENCE-ADJACENT` | closed | 12 | 6 | 1 | 0 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-CREDENTIAL-MAX` | matched | 12 | 6 | 1 | 0 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-FAST-MINIMUMS` | matched | 12 | 3 | 3 | 0 |
| `CLIENT-ADJACENT-PIVOT` | `PRINCIPAL-EVIDENCE-ADJACENT` | matched | 12 | 6 | 1 | 0 |

Observed result:

- The previously open `CLIENT-FAST-ANY` vs `PRINCIPAL-FAST-MINIMUMS` pairing now matched.
- All 9 pairings reached terminal states with 0 invalid attempts.
- Repeated proposal churn was reduced from 15 proposals in the prior attached-fact run to 10 proposals.
- The result matches the earlier terminality target from turn-specific schemas while preserving structured attached fact disclosure.
- One pairing still produced 3 proposals because messages can explicitly reopen a pending proposal to `open`, allowing a revised proposal later.

Decision preserved:

- Keep `proposal_pending` as a first-class negotiation state.
- Keep `send_message` as the mechanism for returning from a pending proposal to open negotiation.

Follow-ups:

- If proposal churn remains undesirable, consider tracking proposal author or proposal revision count rather than forbidding all later proposals after clarification.
- Consider adding explicit `reject_match` separately from `close_negotiation` only if later UX needs to distinguish rejection from broader negotiation closure.

## 2026-09-21: Weak Discovery Live LLM Smoke Test

Model or decision source: OpenAI `gpt-4o-mini` through a dev-only weak discovery runner.

Scenario/matrix: Five-agent weak discovery scenario:

- `marketing_client_agent_1` represents a client seeking marketing work.
- `marketing_client_agent_2` represents a client seeking marketing work.
- `programming_client_agent` represents a client seeking programming work.
- `marketing_principal_agent` represents a principal offering marketing work.
- `programming_principal_agent` represents a principal offering programming work.

Protocol/harness state:

- Weak discovery edges are field-scoped and do not authorize negotiation directly.
- Client agents can choose `probe_weak_connection`, `request_contact`, or `defer` from a turn-specific schema.
- Provider schema constrains targets to currently discoverable same-field agents.
- Weak discovery metadata includes the target represented-party type so client agents can prefer same-field principals over peer client agents.

Initial live run observation:

- Before target represented-party type was included in weak discovery metadata, both marketing client agents chose to connect to each other rather than the marketing principal. This showed that field scoping was respected, but opportunity relevance was under-specified.

Result after adding target represented-party metadata:

| Actor | Chosen Action | Target | Result |
| --- | --- | --- | --- |
| `marketing_client_agent_1` | `request_contact` | `marketing_principal_agent` | active connection created |
| `marketing_client_agent_2` | `request_contact` | `marketing_principal_agent` | active connection created |
| `programming_client_agent` | `request_contact` | `programming_principal_agent` | active connection created |

Aggregate summary:

- Turns: 3
- Valid decisions: 3
- Invalid decisions: 0
- Connections created: 3
- Events: 3 `contact_requested`

Observed result:

- The model respected field-scoped discovery constraints.
- With represented-party type metadata, client-side agents selected same-field principal agents rather than same-field peer client agents.
- The live run validates the deterministic weak discovery slice as a viable starting point for graph formation experiments.

Follow-ups:

- Add a multi-turn discovery-to-negotiation runner where newly created active connections can immediately open negotiation requests.
- Add connection request response semantics before treating connection formation as a mutual relationship rather than a directed active edge.
- Consider adding probe responses so agents can ask before connecting instead of always jumping directly to `request_contact`.

## 2026-09-21: Discovery-To-Negotiation Lifecycle Live Test

Model or decision source: OpenAI `gpt-4o-mini` through dev-only discovery and negotiation runners.

Scenario/matrix: Same five-agent weak discovery scenario as the prior weak discovery smoke test.

Protocol/harness state:

- Client agents first choose a weak discovery action from same-field discoverable agents.
- When a connection is formed, the harness opens and accepts a negotiation over that active connection.
- Each connected client/principal pair runs two negotiation cycles to test whether a later negotiation can be opened after an earlier one reaches terminal state.
- Negotiation turns use the existing turn-specific provider schema, message quota, and `proposal_pending` state.

Important limitation:

- Opening and accepting negotiation requests are currently harness-driven after connection formation. The LLM chooses discovery actions and negotiation actions, but it does not yet emit a first-class `request_negotiation` discovery/graph action.

Result summary:

| Metric | Count |
| --- | ---: |
| Connections created | 3 |
| Negotiations created | 6 |
| Matched negotiations | 4 |
| Closed negotiations | 2 |
| Open negotiations | 0 |
| Errors | 0 |
| Skipped terminal turns | 38 |

Aggregate decisions/events:

- `request_contact`: 3
- `propose_match`: 4
- `accept_match`: 4
- `close_negotiation`: 2
- `contact_requested` events: 3
- `open_negotiation_request` events: 6
- `open_negotiation_response` events: 6
- `match_proposed` events: 4
- `match_accepted` events: 4
- `close_negotiation` events: 2

Observed result:

- Agents formed field-appropriate connections.
- All six harness-opened negotiations reached terminal state: four matched and two closed.
- The harness successfully opened a second negotiation after terminal completion of the first negotiation over the same active connection.
- The high skipped-turn count is expected because each negotiation cycle reserves up to eight turns but often reaches terminal state early.

Follow-ups:

- Add `request_negotiation` as an LLM-emittable action once an active connection exists, so opening negotiations is agent-driven rather than harness-driven.
- Add explicit connection acceptance/rejection semantics if active connections should be mutual rather than immediately created by request.
- Add a combined decision context that lets an agent choose among discovery, connection management, and negotiation actions in one scheduler.

## 2026-09-21: Contact And Agent-Driven Negotiation Request Lifecycle

Model or decision source: OpenAI `gpt-4o-mini` through dev-only discovery and negotiation lifecycle runner.

Protocol/harness state:

- Agent-agent relationships are protocol-facing `contacts`; contacts are directional, not mutual.
- Contact creation is limited to three active outgoing contacts per agent.
- Active negotiations are limited to two per agent; active means `requested`, `open`, or `proposal_pending`.
- Client agents choose `request_contact` through weak discovery.
- Once a contact exists, the client-side LLM emits `request_negotiation`.
- Principal-side LLM then emits `accept_negotiation` before normal negotiation turns begin.

Result summary:

| Metric | Count |
| --- | ---: |
| Contacts created | 3 |
| Negotiation requests emitted | 6 |
| Negotiation accepts emitted | 6 |
| Negotiations created | 6 |
| Matched negotiations | 5 |
| Closed negotiations | 1 |
| Open negotiations | 0 |
| Errors | 0 |

Aggregate decisions/events:

- `request_contact`: 3
- `request_negotiation`: 6
- `accept_negotiation`: 6
- `propose_match`: 5
- `accept_match`: 5
- `close_negotiation`: 1
- `contact_requested` events: 3
- `open_negotiation_request` events: 6
- `open_negotiation_response` events: 6

Observed result:

- Agents successfully formed directional contacts, requested negotiations, accepted inbound negotiation requests, reached terminal outcomes, and opened second negotiations after prior terminal outcomes.
- The small limits did not block this scenario because negotiations terminalized before the second cycle created persistent active-load pressure.

Follow-ups:

- Move from phase-specific harnessing to a unified scheduler/context where agents choose among discovery, contact, request-negotiation, response, and negotiation actions.
- Add tests for the three-contact limit and LLM-facing `request_negotiation` once promoted out of the dev runner.

## 2026-09-21: Unified Agent Lifecycle 10-Agent Run

Model or decision source: OpenAI `gpt-4o-mini` through `scripts.dev.run_unified_agent_lifecycle_experiment`.

Scenario/matrix: 10 agents:

- 3 marketing client agents
- 2 programming client agents
- 2 marketing principal agents
- 2 programming principal agents
- 1 marketing connector/principal-like agent

Protocol/harness state:

- One unified scheduler rotates through all agents.
- Each scheduled agent receives a combined context including weak discovery, directional contacts, contact slots, active negotiations, negotiation slots, inbound requests, valid negotiation actions, and recent negotiation context.
- Agent can choose among discovery/contact actions, `request_negotiation`, negotiation request responses, and normal negotiation actions.
- Contact limit: 3 active outgoing contacts.
- Active negotiation limit: 2 active negotiations per agent.

### 30-turn run

Initial 30-turn result:

| Metric | Count |
| --- | ---: |
| Contacts created | 10 |
| Negotiations created | 9 |
| Requested negotiations | 2 |
| Open negotiations | 7 |
| Errors | 0 |

Decisions:

- `request_contact`: 10
- `request_negotiation`: 9
- `accept_negotiation`: 7
- `send_message`: 4

Observed result:

- The unified scheduler successfully moved beyond contact formation into agent-driven negotiation requests and acceptances.
- 30 turns was not enough for terminal negotiation outcomes; most negotiations were still `open` or `requested`.

### 60-turn run

Extended 60-turn result:

| Metric | Count |
| --- | ---: |
| Contacts created | 10 |
| Negotiations created | 10 |
| Open negotiations | 4 |
| Proposal pending negotiations | 6 |
| Matched negotiations | 0 |
| Closed negotiations | 0 |
| Errors | 1 |

Decisions:

- `request_contact`: 10
- `request_negotiation`: 10
- `accept_negotiation`: 10
- `send_message`: 23
- `propose_match`: 6
- `accept_match`: 1

Observed result:

- The larger run successfully exercised the full unified action space through contact creation, negotiation request, negotiation acceptance, messages, and proposals.
- It did not reach terminal outcomes within 60 turns. Six negotiations ended in `proposal_pending`, and four remained `open`.
- One invalid/protocol error occurred when the model emitted `accept_match` while choosing a negotiation that did not have a pending proposal. This exposes a schema weakness in the unified runner: action availability is currently unioned across all active negotiations instead of being tied to a selected negotiation/action pair.

Decision/change:

- The unified scheduler is a useful calibration harness, but it needs state-constrained action/negotiation pairing before we treat its live outcomes as comparable to the pairwise runs.

Follow-ups:

- Change the unified schema so selected `action` and `negotiation_id` are coupled, likely by scheduling or selecting a focus negotiation before constraining actions.
- Consider ending a negotiation turn as soon as a proposal is pending by scheduling the proposal recipient sooner, rather than waiting for round-robin order across all 10 agents.
- Track contact utility: contacts that lead to negotiation request, accepted negotiation, proposal, match, or close.

### Follow-up: focused negotiation schema

Protocol/harness change:

- The unified runner now selects at most one focus negotiation per scheduled turn.
- If a focus negotiation exists, the provider schema exposes only that negotiation's valid actions and constrains `negotiation_id` to that negotiation.
- Discovery/contact/request-negotiation actions are exposed only when no current focus negotiation requires attention.

60-turn result after fix:

| Metric | Count |
| --- | ---: |
| Contacts created | 10 |
| Negotiations created | 8 |
| Open negotiations | 5 |
| Proposal pending negotiations | 3 |
| Errors | 0 |

100-turn result after fix:

| Metric | Count |
| --- | ---: |
| Contacts created | 10 |
| Negotiations created | 17 |
| Matched negotiations | 5 |
| Closed negotiations | 4 |
| Open negotiations | 7 |
| Requested negotiations | 1 |
| Errors | 0 |

100-turn aggregate decisions:

- `request_contact`: 10
- `request_negotiation`: 17
- `accept_negotiation`: 15
- `reject_negotiation`: 1
- `send_message`: 41
- `propose_match`: 8
- `accept_match`: 5
- `close_negotiation`: 3

Observed result:

- The action/negotiation mismatch error was eliminated.
- Longer unified scheduling now reaches terminal outcomes while continuing to form contacts and open new negotiations.
- Some negotiations remain open/requested at 100 turns, so scheduler priority and turn allocation now matter more than schema validity.

Follow-ups:

- Consider scheduling agents with pending proposals or inbound requests ahead of ordinary round-robin turns.
- Consider stricter pressure after message budget exhaustion in the unified runner, similar to the pairwise runner's terminal pressure.

## 2026-09-21: Initial Bandwidth Sweep

Model or decision source: OpenAI `gpt-4o-mini` through `scripts.dev.run_bandwidth_sweep_experiment`.

Scenario/matrix: Unified 10-agent lifecycle market.

Protocol/harness state:

- Focused negotiation schema active.
- Contact and active negotiation limits parameterized in the unified runner.
- Message quota remained fixed at 3 messages per actor per negotiation for this initial sweep.
- Sweep varied contact limit and active negotiation limit only.

Sweep parameters:

- Turns per run: 60
- Repetitions per configuration: 2
- Contact limits: 1, 3
- Active negotiation limits: 1, 2

Aggregate result:

| Contact Limit | Negotiation Limit | Avg Contacts | Avg Negotiations | Avg Matched | Avg Closed | Avg Open | Avg Proposal Pending | Avg Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 10.0 | 8.5 | 0.0 | 1.0 | 4.5 | 3.0 | 0.0 |
| 1 | 2 | 10.0 | 9.0 | 1.0 | 0.0 | 5.0 | 3.0 | 0.0 |
| 3 | 1 | 10.0 | 8.5 | 0.5 | 1.5 | 4.5 | 2.0 | 0.0 |
| 3 | 2 | 10.0 | 8.5 | 0.0 | 0.5 | 4.5 | 3.5 | 0.0 |

Observed result:

- All configurations created 10 contacts: one per scheduled agent in the 10-agent scenario. The contact limit did not bind in this setup because each agent only needed one useful same-field contact before negotiation actions became higher priority.
- Active negotiation limit showed small effects but the sample is too small to infer strong direction. Limit 2 produced one matched negotiation in the contact-limit-1 condition but more proposal-pending leftovers in the contact-limit-3 condition.
- Error rate remained 0 across the sweep, suggesting the focused schema is stable under repeated live runs.
- Most negotiations were still open or proposal-pending after 60 turns, so turn budget/scheduler pressure is currently a stronger bottleneck than contact limit.

Follow-ups:

- Run a larger sweep with more repetitions after adding priority scheduling for inbound requests and proposal-pending negotiations.
- Add a scenario where contact limit can bind, e.g. more weak-discoverable targets per agent and fewer immediately useful principal contacts.
- Parameterize message quota in the application service before sweeping message bandwidth.

## 2026-09-22: Networking-Only Workflow Runner

Model or decision source: OpenAI `gpt-4o-mini` through `scripts.dev.run_networking_experiment`; deterministic injected policy in tests.

Scenario/matrix: Same 10-agent weak discovery/contact scenario used by the unified lifecycle runner.

Protocol/harness state:

- Negotiation work and networking work are separated for experiments.
- Negotiation experiments remain bounded two-party workflows where the endpoint is a terminal negotiation state: `matched` or `closed`.
- Networking experiments expose broader weak discovery/contact/capacity context and stop the scheduled agent's workflow once that agent opens a negotiation request.
- The networking runner does not accept, message, propose, accept match, or close negotiations after the request is opened.

Decision/change:

- Added `scripts.dev.run_networking_experiment`.
- The networking action schema permits `request_contact`/`probe_weak_connection` when no relevant contact exists, and narrows to `request_negotiation` once the actor has a contact and negotiation capacity.
- Added deterministic tests proving the action-priority split and that an actor workflow is considered complete once it creates a negotiation request.

Live smoke result:

| Metric | Count |
| --- | ---: |
| Turns | 30 |
| Contacts created | 12 |
| Negotiations requested | 9 |
| Workflows completed | 9 |
| Workflow completion rate | 0.9 |
| Errors | 0 |

Aggregate decisions/events:

- `request_contact`: 12
- `request_negotiation`: 9
- `contact_requested` events: 12
- `open_negotiation_request` events: 9

Observed result:

- The split is useful: the runner measures contact-to-negotiation opening behavior without conflating it with negotiation terminality.
- Most agents completed the networking endpoint within 30 turns.
- The runner still prioritizes opening a negotiation after the first contact, so future networking scenarios must make multiple contacts strategically useful before contact limits will bind.

Verification:

- `python -m pytest tests/test_networking_experiment.py` passed: 3 tests.
- `python -m pytest` passed: 137 tests.

Follow-ups:

- Add a networking scenario where one agent represents multiple parties or has multiple plausible contact targets before a negotiation should be opened.
- Add hidden match-quality scoring so opening a negotiation with the first plausible contact can be compared against opening the best available contact.
- Preserve the single-topic context boundary for negotiation experiments: once a negotiation is open, do not expose unrelated contacts or represented parties in that negotiation context.

## 2026-09-22: Multi-Party Topic-Selection Networking Smoke Test

Model or decision source: OpenAI `gpt-4o-mini` through `scripts.dev.run_topic_selection_networking_experiment`; deterministic injected policy in tests.

Scenario/matrix:

- `client_portfolio_agent` represents two clients: a marketing generalist and a backend engineer.
- `principal_portfolio_agent` represents two principals/openings: a marketing coordinator role and a data engineering role.
- A directional contact already exists from the client-side portfolio agent to the principal-side portfolio agent.

Protocol/harness state:

- This is a networking/topic-selection experiment, not a negotiation experiment.
- The workflow endpoint is creating one `open_negotiation_request`.
- The request subject must include exactly one client topic and exactly one principal topic.
- Accepting-agent counter-offers, topic substitution, and partial topic proposals remain open protocol-design questions.

Decision/change:

- Added `seed_multi_party_contact_scenario` for the smallest portfolio-agent contact case.
- Added `scripts.dev.run_topic_selection_networking_experiment` to run one client-side networking turn over the existing contact.
- Added tests for schema-constrained topic selection, successful topic-pair negotiation creation, and rejection of unrepresented topics.

Live smoke result:

| Metric | Value |
| --- | --- |
| Negotiations requested | 1 |
| Open negotiation request events | 1 |
| Selected client topic | `client_marketing_generalist` |
| Selected principal topic | `principal_marketing_role` |
| Exactly one client topic | true |
| Exactly one principal topic | true |

Observed result:

- The model chose the clearly aligned marketing client + marketing role pair over the less-aligned backend/data pair.
- The runner cleanly records the selected topic pair in the negotiation subject without entering two-party negotiation.

Verification:

- `python -m pytest tests/test_topic_selection_networking_experiment.py` passed: 3 tests.
- `python -m pytest` passed: 140 tests.

Follow-ups:

- Decide whether the proposer should always include both topics, or whether partial topic proposals should be allowed.
- Decide whether the accepting agent may accept, fill missing topics, counter with a different topic pair, or reject.
- Once topic-open protocol is clearer, feed the opened topic pair into the bounded single-topic negotiation context.

### Follow-up: 10 repeated topic-selection runs

Run parameters:

- Runner: `scripts.dev.run_topic_selection_networking_experiment`
- Model: OpenAI `gpt-4o-mini`
- Repetitions: 10 independent 1-turn runs

Aggregate result:

| Selected Client Topic | Selected Principal Topic | Count |
| --- | --- | ---: |
| `client_marketing_generalist` | `principal_marketing_role` | 10 |

Protocol shape:

- Valid exactly-one-client-topic subjects: 10/10
- Valid exactly-one-principal-topic subjects: 10/10
- Negotiation requests created: 10/10

Interpretation:

- The current schema and prompt reliably produce a well-formed two-topic negotiation request in this simple scenario.
- Because one pair is obviously aligned and the alternatives are weakly aligned, this scenario tests protocol shape more than nuanced ranking.
- The model's repeated choice suggests that a required `(client_topic_id, principal_topic_id)` request is a stable baseline for the first topic-selection protocol.

Follow-ups:

- Add a harder ambiguous scenario where both principal topics are plausible for the same client or both clients are plausible for the same principal.
- Add an accepting-agent response experiment: accept exact topic pair, reject, or counter with a different represented topic pair.

### Follow-up: ambiguous 10 repeated topic-selection runs

Protocol/harness change:

- Added `--scenario-kind ambiguous` to `scripts.dev.run_topic_selection_networking_experiment`.
- The ambiguous scenario has two plausible diagonal topic pairs:
  - backend API client + platform API role, emphasizing strong role fit and growth path;
  - data pipeline client + data platform role, emphasizing quick placement and soon-to-fill data pipeline ownership.

Run parameters:

- Runner: `scripts.dev.run_topic_selection_networking_experiment --scenario-kind ambiguous`
- Model: OpenAI `gpt-4o-mini`
- Repetitions: 10 independent 1-turn runs

Aggregate result:

| Selected Client Topic | Selected Principal Topic | Count |
| --- | --- | ---: |
| `client_data_pipeline_engineer` | `principal_data_platform_role` | 8 |
| `client_backend_api_engineer` | `principal_platform_api_role` | 2 |

Protocol shape:

- Valid exactly-one-client-topic subjects: 10/10
- Valid exactly-one-principal-topic subjects: 10/10
- Negotiation requests created: 10/10

Interpretation:

- The required two-topic request shape remained stable under a more ambiguous choice.
- The model mostly favored the data/data-platform pair. The reasons repeatedly cited data-pipeline alignment and quick placement / soon-to-fill urgency.
- The backend/platform pair appeared in 2 of 10 runs, with reasons emphasizing backend strength and growth-path fit.
- This suggests the current context is sufficient for basic tradeoff behavior, but priorities are unweighted natural language. If portfolio behavior needs to be predictable, we likely need explicit priority/ranking fields rather than relying on free-text summaries.

Follow-ups:

- Add explicit priority weights or strategy labels to represented topics and test whether choices shift predictably.
- Add accepting-agent topic-response protocol next: accept exact pair, reject, or counter with a different pair.

## 2026-09-22: Partial Topic Proposal And Responder Fill Test

Model or decision source: OpenAI `gpt-4o-mini` through `scripts.dev.run_partial_topic_proposal_experiment`; deterministic injected policy in tests.

Scenario/matrix: Ambiguous two-plausible-pair portfolio contact scenario.

Protocol/harness state:

- The client-side portfolio agent proposes exactly one of its own client topics, without selecting the contact's principal topic.
- The principal-side portfolio agent responds by either accepting with exactly one represented principal topic or rejecting without selecting a principal topic.
- If accepted, the harness opens an `open_negotiation_request` whose subject contains exactly one client topic and one responder-filled principal topic.

Decision/change:

- Added `scripts.dev.run_partial_topic_proposal_experiment`.
- Added tests for accept-with-principal-topic, reject-without-negotiation, and malformed reject validation.

Repeated live result:

| Proposed Client Topic | Responder Principal Topic | Count |
| --- | --- | ---: |
| `client_data_pipeline_engineer` | `principal_data_platform_role` | 10 |

Protocol shape:

- Proposals created with exactly one client topic: 10/10
- Responses accepted with exactly one principal topic: 10/10
- Rejections: 0/10
- Negotiation requests created after acceptance: 10/10

Interpretation:

- The partial-topic flow is structurally viable: the proposer can limit itself to its own candidate, and the responder can fill the principal side to produce a complete negotiation topic pair.
- In this scenario, proposer choice became more concentrated than the prior both-topics experiment: data pipeline candidate was selected 10/10, versus 8/10 when the proposer chose both topics.
- This likely happened because the proposing context says the contact represents principal topics but hides exact principal topics; the client-side agent leaned toward the candidate with broadly legible data/placement relevance rather than the backend growth-path candidate.
- The responder consistently selected the data platform role and never rejected, which is expected because a strong matching principal topic existed.

Follow-ups:

- Add a no-good-fit variant to test whether the responder rejects when no represented principal topic fits the proposed client topic.
- Add a mismatch variant where the proposer chooses a plausible candidate but the responder's best available principal topic is weaker, to observe whether it accepts marginal fit or rejects.
- Consider whether partial topic proposals should be represented as their own persisted protocol event before a negotiation request exists, rather than only as runner transcript state.

### Follow-up: bad-fit rejection runs

Protocol/harness change:

- Added `--scenario-kind bad-fit` to `scripts.dev.run_partial_topic_proposal_experiment`.
- Client topics are deliberately unrelated to principal topics:
  - clients: hospitality barista, graphic designer;
  - principals: senior ML engineer, security architect.

Run parameters:

- Runner: `scripts.dev.run_partial_topic_proposal_experiment --scenario-kind bad-fit`
- Model: OpenAI `gpt-4o-mini`
- Repetitions: 10 independent proposal/response runs

Aggregate result:

| Proposed Client Topic | Count |
| --- | ---: |
| `client_barista` | 6 |
| `client_graphic_designer` | 4 |

Response result:

| Response | Count |
| --- | ---: |
| `reject_client_topic` | 10 |
| `accept_with_principal_topic` | 0 |

Protocol outcome:

- Accepted: 0/10
- Negotiation requests created: 0/10
- Rejections selected no principal topic: 10/10

Interpretation:

- The responder reliably rejected deliberately-bad proposals instead of forcing a weak principal topic.
- The proposer varied between its two bad client topics, but this did not affect responder discipline.
- This supports partial-topic proposal as a safe opening protocol when paired with a responder-side reject path.

Follow-ups:

- Add a marginal-fit scenario to find the acceptance threshold between obvious accept and obvious reject.
- Consider persisting partial-topic proposal/rejection as pre-negotiation contact events if this flow becomes product behavior rather than only experiment harness behavior.
