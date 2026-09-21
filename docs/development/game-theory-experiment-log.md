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
