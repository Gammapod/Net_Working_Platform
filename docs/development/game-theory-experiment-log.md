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
