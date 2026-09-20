# LLM Decision Contract

This document defines the LLM-facing protocol surface for supervised decision experiments.

The contract describes the only JSON decision signals an LLM may emit. It does not decide whether a model chose the best action for a scenario. It only defines whether the emitted decision is well-formed, supported, and safe to pass to a later executor.

## Principles

- The LLM receives read-only decision context.
- The LLM emits exactly one JSON object.
- The JSON object must have an `action` field.
- The action must be one of the supported action values below.
- Each action permits only its documented fields.
- Unknown actions, missing required fields, wrong field types, and extra fields are invalid.
- Valid decisions are still subject to application service authorization and protocol validation before execution.

## Supported Actions

### `accept_negotiation`

Accept a requested negotiation.

Required fields:

- `action`: `"accept_negotiation"`
- `negotiation_id`: string
- `actor_agent_id`: string

### `reject_negotiation`

Reject a requested negotiation.

Required fields:

- `action`: `"reject_negotiation"`
- `negotiation_id`: string
- `actor_agent_id`: string

Optional fields:

- `reason`: string

### `send_message`

Send a free-form negotiation message.

Required fields:

- `action`: `"send_message"`
- `negotiation_id`: string
- `actor_agent_id`: string
- `body`: string

### `propose_match`

Propose a match in an open negotiation.

Required fields:

- `action`: `"propose_match"`
- `negotiation_id`: string
- `actor_agent_id`: string
- `proposal`: object

### `accept_match`

Accept a previously proposed match.

Required fields:

- `action`: `"accept_match"`
- `negotiation_id`: string
- `actor_agent_id`: string

### `close_negotiation`

Close an open negotiation.

Required fields:

- `action`: `"close_negotiation"`
- `negotiation_id`: string
- `actor_agent_id`: string
- `reason`: string

### `defer`

Choose no protocol mutation for now.

Required fields:

- `action`: `"defer"`
- `actor_agent_id`: string
- `reason`: string

## Non-Goals

- This contract does not grant database access.
- This contract does not execute decisions.
- This contract does not evaluate decision quality.
- This contract does not replace domain or application service validation.
