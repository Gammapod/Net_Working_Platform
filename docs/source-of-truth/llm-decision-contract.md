# LLM Decision Contract

This document defines the LLM-facing protocol surface for supervised decision experiments.

The contract describes the only JSON decision signals an LLM may emit. It does not decide whether a model chose the best action for a scenario. It only defines whether the emitted decision is well-formed, supported, and safe to pass to a later executor.

## Principles

- The LLM receives read-only decision context.
- The LLM emits exactly one JSON object.
- Providers that support structured output should be constrained with the JSON Schema for this contract.
- The JSON object must have an `action` field.
- The action must be one of the supported action values below.
- Each action permits only its documented fields.
- Substantive open-negotiation actions may optionally attach `disclose_fact_fields` to disclose currently available represented-party facts before the action executes.
- Fact disclosure is not a standalone action.
- Unknown actions, missing required fields, wrong field types, and extra fields are invalid.
- Valid decisions are still subject to application service authorization and protocol validation before execution.

## JSON Schema

The machine-readable schema is exposed in code as `LLM_DECISION_JSON_SCHEMA` from `net_working_platform.application.llm_decisions` and should be included in provider context packages when possible.

The schema is the preferred provider-facing constraint. Prose instructions are a fallback for providers or tools that do not support JSON Schema response formats.

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

Optional fields:

- `disclose_fact_fields`: array of strings naming currently available represented-party fact fields to disclose before the message is appended.

### `propose_match`

Propose a match in an open negotiation.

Required fields:

- `action`: `"propose_match"`
- `negotiation_id`: string
- `actor_agent_id`: string
- `proposal`: object

Optional fields:

- `disclose_fact_fields`: array of strings naming currently available represented-party fact fields to disclose before the match proposal is appended.

### `accept_match`

Accept a previously proposed match.

Required fields:

- `action`: `"accept_match"`
- `negotiation_id`: string
- `actor_agent_id`: string

Optional fields:

- `disclose_fact_fields`: array of strings naming currently available represented-party fact fields to disclose before match acceptance is appended.

### `close_negotiation`

Close an open negotiation.

Required fields:

- `action`: `"close_negotiation"`
- `negotiation_id`: string
- `actor_agent_id`: string
- `reason`: string

Optional fields:

- `disclose_fact_fields`: array of strings naming currently available represented-party fact fields to disclose before the close event is appended.

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
