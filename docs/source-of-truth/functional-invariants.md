# Functional Invariants

This is the source of truth for MVP protocol behavior. Every automated test that protects product behavior should reference one or more invariant IDs from this document.

## Scope

The MVP is a graph-backed communication platform for representative agents. Agents represent clients and principals, maintain graph edges, and run structured negotiations over established agent-agent connections.

## Entity Invariants

### INV-E-001: Agents Are Graph Nodes

An agent is a graph node that can hold agent-agent edges and representation edges.

Protected by:

- Planned: `test_create_agent_persists_agent_node`
- `test_agent_node_uses_agent_type`
- `test_sql_repositories_round_trip_core_graph_records`
- `test_storage_schema_declares_mvp_tables`

### INV-E-002: Clients And Principals Are Distinct Node Types

Clients/jobseekers and principals/hirers are graph nodes distinct from agents.

Protected by:

- Planned: `test_client_and_principal_node_types_are_distinct`
- `test_client_and_principal_node_types_are_distinct`
- `test_core_table_columns_match_repository_contracts`

### INV-E-003: Representation Edges Are Not Agent-Agent Edges

An agent-client or agent-principal representation edge is a different relationship type from an agent-agent communication edge.

Protected by:

- Planned: `test_representation_edges_are_separate_from_agent_connections`
- `test_representation_edges_are_separate_from_agent_connections`
- `test_sql_repositories_round_trip_core_graph_records`

## Edge Invariants

### INV-G-001: Agent-Agent Communication Requires An Active Edge

An agent may request a negotiation with another agent only when there is an active agent-agent edge between them.

Protected by:

- Planned: `test_request_negotiation_requires_active_agent_connection`
- `test_request_negotiation_requires_active_agent_connection`
- `test_request_negotiation_service_requires_active_connection`
- `test_agent_connections_are_directional`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-G-002: Inactive Edges Preserve History

Setting an edge inactive must not delete prior messages, negotiations, or events.

Protected by:

- Planned: `test_inactive_edge_preserves_history`

### INV-G-003: Edge State Is A Snapshot, Events Are The Record

Current edge state may be stored for retrieval, but state changes must also be represented by append-only events.

Protected by:

- Planned: `test_edge_state_change_appends_event`

## Negotiation Protocol Invariants

### INV-N-001: Negotiations Are First-Class Records

A negotiation is its own record. It is not only an edge state or a message thread.

Protected by:

- Planned: `test_request_negotiation_creates_negotiation_record`
- `test_open_negotiation_request_creates_requested_state`
- `test_request_negotiation_service_creates_record_and_event`
- `test_sql_repositories_round_trip_negotiation_and_events_in_order`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-002: Negotiation Starts Requested

An `open_negotiation_request` creates a negotiation in `requested` state.

Protected by:

- Planned: `test_open_negotiation_request_creates_requested_negotiation`
- `test_open_negotiation_request_creates_requested_state`
- `test_request_negotiation_service_creates_record_and_event`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-003: Requested Negotiation May Be Accepted Or Rejected

A negotiation in `requested` state may transition to `open` through accept or `closed` through reject.

Protected by:

- `test_accept_requested_negotiation_opens`
- `test_reject_requested_negotiation_closes`
- `test_accept_negotiation_service_opens_requested_negotiation`
- `test_reject_negotiation_service_closes_requested_negotiation`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-004: Messages Require Open Negotiation

Free-form negotiation messages are valid only while the negotiation is `open`.

Protected by:

- `test_message_keeps_open_negotiation_open`
- `test_message_requires_open_negotiation`
- `test_send_message_service_appends_message_event_for_open_negotiation`
- `test_send_message_service_rejects_non_open_negotiation`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-005: Match Acceptance Requires Match Proposal

`match_accepted` is valid only after a `match_proposed` event in the same open negotiation.

Protected by:

- `test_match_proposal_keeps_negotiation_open`
- `test_match_acceptance_requires_prior_proposal`
- `test_match_acceptance_closes_as_matched_after_proposal`
- `test_propose_match_service_appends_event_for_open_negotiation`
- `test_accept_match_service_requires_prior_proposal`
- `test_accept_match_service_marks_negotiation_matched`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-006: Matched And Closed Are Terminal

No protocol action may reopen or mutate a negotiation after it reaches `matched` or `closed`, except append-only audit/read-model events that do not change status.

Protected by:

- Planned: `test_closed_negotiation_rejects_messages`
- Planned: `test_matched_negotiation_rejects_close`
- `test_closed_negotiation_rejects_messages`
- `test_matched_negotiation_rejects_close`
- `test_close_negotiation_service_closes_open_negotiation`

### INV-N-007: Negotiation Actions Require Participant Actor

Only the negotiation's `from_agent_id` or `to_agent_id` may perform protocol actions on that negotiation. Rejected non-participant actions must not mutate negotiation state or append protocol events.

Protected by:

- `test_non_participant_cannot_respond_to_negotiation`
- `test_non_participant_cannot_send_message`
- `test_non_participant_cannot_propose_match`
- `test_non_participant_cannot_accept_match`
- `test_non_participant_cannot_close_negotiation`

## Event And History Invariants

### INV-H-001: Every Protocol Action Appends An Event

Every protocol action must create an append-only event with actor, timestamp, negotiation or edge reference, type, and payload.

Protected by:

- Planned: `test_protocol_action_appends_event`
- `test_request_negotiation_service_creates_record_and_event`
- `test_accept_negotiation_service_opens_requested_negotiation`
- `test_reject_negotiation_service_closes_requested_negotiation`
- `test_send_message_service_appends_message_event_for_open_negotiation`
- `test_propose_match_service_appends_event_for_open_negotiation`
- `test_accept_match_service_marks_negotiation_matched`
- `test_close_negotiation_service_closes_open_negotiation`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-H-002: Event History Is Append-Only

Existing events must not be updated or deleted through application services.

Protected by:

- Planned: `test_events_are_append_only`

### INV-H-003: Retrieval APIs Return Structured History

History retrieval must return structured records, not only concatenated text.

Protected by:

- Planned: `test_retrieve_negotiation_history_returns_structured_events`
- `test_retrieve_negotiation_history_returns_structured_events`
- `test_sql_repositories_round_trip_negotiation_and_events_in_order`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-H-004: Agent Decision Context Is Structured And Read-Only

Agent decision context retrieval must return structured, JSON-friendly data for a single agent without mutating negotiations or appending protocol events. The context must include active load, capacity information when supplied, inbound requested negotiations, open negotiations, recent protocol events relevant to that agent, the full supported protocol action list, and valid next actions by active negotiation state.

Protected by:

- `test_get_agent_decision_context_returns_structured_read_only_context`
- `test_cli_returns_agent_decision_context`
- `test_get_agent_decision_context_includes_capacity_when_limit_supplied`

## LLM Decision Invariants

### INV-L-001: LLM Decisions Use A Closed Action Set

LLM decision signals must use exactly one supported action from the LLM decision contract. Unsupported actions are invalid.

Protected by:

- `test_parse_llm_accept_negotiation_decision`
- `test_parse_llm_decision_rejects_unknown_action`

### INV-L-002: LLM Decisions Reject Malformed Payloads

LLM decision signals must include all required fields for their action, use the expected field types, and reject extra fields.

Protected by:

- `test_parse_llm_accept_negotiation_decision`
- `test_parse_llm_decision_requires_action_specific_fields`
- `test_parse_llm_decision_rejects_extra_fields`

### INV-L-005: LLM Decision Contract Exposes JSON Schema

The LLM decision contract must expose a machine-readable JSON Schema so providers that support structured output can be constrained by schema instead of prose alone.

Protected by:

- `test_llm_decision_json_schema_describes_supported_actions`
- `test_context_only_package_outputs_provider_neutral_prompt_without_execution`

### INV-L-006: Dev Provider Adapters Use Schema-Constrained Output

Dev-only provider adapters must use the LLM decision JSON Schema as the provider output constraint when the provider supports schema-constrained responses. Provider credentials must be read from environment variables, not stored in repository files.

Protected by:

- `test_openai_adapter_builds_schema_constrained_responses_request`
- `test_openai_adapter_parses_schema_constrained_decision_text`
- `test_openai_adapter_requires_api_key`

### INV-L-003: LLM Defer Is Explicit And Non-Mutating

A model may choose `defer` only as an explicit structured decision with an actor and reason. `defer` represents no protocol mutation by itself.

Protected by:

- `test_parse_llm_defer_decision`

### INV-L-004: Validated LLM Decisions Execute Through Application Services

LLM decision execution must accept validated decision objects, not raw model JSON. Mutating decisions must execute through application services so normal protocol authorization, state transitions, and event appends remain enforced. `defer` must not mutate protocol state.

Protected by:

- `test_execute_llm_accept_negotiation_decision_uses_service`
- `test_execute_llm_reject_negotiation_decision_uses_service`
- `test_execute_llm_send_message_decision_uses_service`
- `test_execute_llm_propose_match_decision_uses_service`
- `test_execute_llm_accept_match_decision_uses_service`
- `test_execute_llm_close_negotiation_decision_uses_service`
- `test_execute_llm_defer_decision_does_not_mutate_protocol_state`
- `test_supervised_llm_accept_experiment_validates_executes_and_records_event`

## Capacity Invariants

### INV-C-001: Open Negotiation Limit Is Enforced

An agent cannot exceed its configured maximum active negotiations. Active load includes `requested` and `open` negotiations where the agent is either `from_agent_id` or `to_agent_id`. `matched` and `closed` negotiations do not count as active load.

Protected by:

- Planned: `test_open_negotiation_limit_enforced`
- `test_open_negotiation_capacity_allows_below_limit`
- `test_open_negotiation_capacity_rejects_at_limit`
- `test_request_negotiation_service_rejects_when_actor_at_capacity`
- `test_sql_negotiation_repository_counts_requested_and_open_as_active_load`
- `test_sql_negotiation_repository_counts_inbound_requested_and_open_as_active_load`

### INV-C-002: Capacity Rejections Are Recorded

A protocol action rejected due to capacity must append an event explaining the rejection.

Protected by:

- Planned: `test_capacity_rejection_appends_event`
- `test_request_negotiation_service_rejects_when_actor_at_capacity`

## CLI Invariants

### INV-CLI-001: CLI Commands Return Structured JSON

Human-first CLI commands must return structured JSON so outputs can be inspected by humans and reused by scripts or future agent tools.

Protected by:

- `test_cli_runs_full_negotiation_lifecycle`
- `test_cli_returns_agent_decision_context`

### INV-CLI-002: CLI Uses The Same Application Services As Other Entrypoints

CLI commands must call the same application services and SQL repositories used by tests and future agent tools, rather than implementing separate protocol behavior.

Protected by:

- `test_cli_runs_full_negotiation_lifecycle`
- `test_cli_returns_agent_decision_context`

## Test Traceability

| Test | Invariants |
| --- | --- |
| `test_domain_smoke` | INV-N-004 |
| `test_open_negotiation_request_creates_requested_state` | INV-N-001, INV-N-002 |
| `test_accept_requested_negotiation_opens` | INV-N-003 |
| `test_reject_requested_negotiation_closes` | INV-N-003 |
| `test_message_keeps_open_negotiation_open` | INV-N-004 |
| `test_message_requires_open_negotiation` | INV-N-004 |
| `test_match_proposal_keeps_negotiation_open` | INV-N-005 |
| `test_match_acceptance_requires_prior_proposal` | INV-N-005 |
| `test_match_acceptance_closes_as_matched_after_proposal` | INV-N-005 |
| `test_closed_negotiation_rejects_messages` | INV-N-006 |
| `test_matched_negotiation_rejects_close` | INV-N-006 |
| `test_agent_node_uses_agent_type` | INV-E-001 |
| `test_client_and_principal_node_types_are_distinct` | INV-E-002 |
| `test_representation_edges_are_separate_from_agent_connections` | INV-E-003 |
| `test_request_negotiation_requires_active_agent_connection` | INV-G-001 |
| `test_open_negotiation_capacity_allows_below_limit` | INV-C-001 |
| `test_open_negotiation_capacity_rejects_at_limit` | INV-C-001 |
| `test_request_negotiation_service_requires_active_connection` | INV-G-001 |
| `test_request_negotiation_service_creates_record_and_event` | INV-N-001, INV-N-002, INV-H-001 |
| `test_request_negotiation_service_rejects_when_actor_at_capacity` | INV-C-001, INV-C-002 |
| `test_accept_negotiation_service_opens_requested_negotiation` | INV-N-003, INV-H-001 |
| `test_reject_negotiation_service_closes_requested_negotiation` | INV-N-003, INV-H-001 |
| `test_send_message_service_appends_message_event_for_open_negotiation` | INV-N-004, INV-H-001 |
| `test_send_message_service_rejects_non_open_negotiation` | INV-N-004 |
| `test_propose_match_service_appends_event_for_open_negotiation` | INV-N-005, INV-H-001 |
| `test_accept_match_service_requires_prior_proposal` | INV-N-005 |
| `test_accept_match_service_marks_negotiation_matched` | INV-N-005, INV-H-001 |
| `test_close_negotiation_service_closes_open_negotiation` | INV-N-006, INV-H-001 |
| `test_retrieve_negotiation_history_returns_structured_events` | INV-H-003 |
| `test_storage_schema_declares_mvp_tables` | INV-E-001 |
| `test_agent_connections_are_directional` | INV-G-001 |
| `test_core_table_columns_match_repository_contracts` | INV-E-002 |
| `test_storage_schema_uses_check_constraints_for_domain_enums` | INV-E-001, INV-E-002, INV-N-002, INV-N-006 |
| `test_sql_repositories_round_trip_core_graph_records` | INV-E-001, INV-E-003 |
| `test_sql_negotiation_repository_counts_requested_and_open_as_active_load` | INV-C-001 |
| `test_sql_negotiation_repository_counts_inbound_requested_and_open_as_active_load` | INV-C-001 |
| `test_sql_repositories_round_trip_negotiation_and_events_in_order` | INV-N-001, INV-H-003 |
| `test_sql_backed_negotiation_service_runs_full_lifecycle` | INV-G-001, INV-N-001, INV-N-002, INV-N-003, INV-N-004, INV-N-005, INV-H-001, INV-H-003 |
| `test_cli_runs_full_negotiation_lifecycle` | INV-CLI-001, INV-CLI-002, INV-G-001, INV-N-001, INV-N-002, INV-N-003, INV-N-004, INV-N-005, INV-H-003 |
| `test_non_participant_cannot_respond_to_negotiation` | INV-N-007 |
| `test_non_participant_cannot_send_message` | INV-N-007 |
| `test_non_participant_cannot_propose_match` | INV-N-007 |
| `test_non_participant_cannot_accept_match` | INV-N-007 |
| `test_non_participant_cannot_close_negotiation` | INV-N-007 |
| `test_get_agent_decision_context_returns_structured_read_only_context` | INV-H-004 |
| `test_get_agent_decision_context_includes_capacity_when_limit_supplied` | INV-H-004 |
| `test_get_agent_decision_context_includes_accept_match_after_match_proposal` | INV-H-004 |
| `test_cli_returns_agent_decision_context` | INV-H-004, INV-CLI-001, INV-CLI-002 |
| `test_inbound_request_scenario_produces_observable_decision_context` | INV-G-001, INV-N-002, INV-H-001, INV-H-004 |
| `test_referral_relay_scenario_produces_intermediary_with_two_open_negotiations` | INV-G-001, INV-N-003, INV-N-004, INV-H-001, INV-H-004 |
| `test_parallel_inbound_scenario_exposes_two_requested_negotiations` | INV-G-001, INV-N-002, INV-H-001, INV-H-004, INV-C-001 |
| `test_parse_llm_accept_negotiation_decision` | INV-L-001, INV-L-002 |
| `test_parse_llm_decision_rejects_unknown_action` | INV-L-001 |
| `test_parse_llm_decision_requires_action_specific_fields` | INV-L-002 |
| `test_parse_llm_decision_rejects_extra_fields` | INV-L-002 |
| `test_parse_llm_defer_decision` | INV-L-003 |
| `test_execute_llm_accept_negotiation_decision_uses_service` | INV-L-004, INV-N-003, INV-H-001 |
| `test_execute_llm_reject_negotiation_decision_uses_service` | INV-L-004, INV-N-003, INV-H-001 |
| `test_execute_llm_send_message_decision_uses_service` | INV-L-004, INV-N-004, INV-H-001 |
| `test_execute_llm_propose_match_decision_uses_service` | INV-L-004, INV-N-005, INV-H-001 |
| `test_execute_llm_accept_match_decision_uses_service` | INV-L-004, INV-N-005, INV-H-001 |
| `test_execute_llm_close_negotiation_decision_uses_service` | INV-L-004, INV-N-006, INV-H-001 |
| `test_execute_llm_defer_decision_does_not_mutate_protocol_state` | INV-L-003, INV-L-004 |
| `test_supervised_llm_accept_experiment_validates_executes_and_records_event` | INV-L-001, INV-L-002, INV-L-004, INV-N-003, INV-H-001 |
| `test_supervised_experiment_runner_outputs_database_backed_structured_event_log` | INV-H-001, INV-H-003, INV-L-001, INV-L-002, INV-L-004 |
| `test_context_only_package_outputs_provider_neutral_prompt_without_execution` | INV-H-004, INV-L-001, INV-L-002 |
| `test_existing_agent_context_package_describes_open_negotiation_history` | INV-H-004, INV-L-001, INV-L-004 |
| `test_context_only_package_can_describe_at_capacity_agent` | INV-H-004 |
| `test_fit_context_package_describes_request_subject_and_fit_criteria` | INV-H-004 |
| `test_fit_context_package_can_describe_bad_fit_request` | INV-H-004 |
| `test_fit_context_package_can_describe_ambiguous_fit_request` | INV-H-004 |
| `test_execute_decision_against_existing_scenario_reuses_prepared_database` | INV-H-001, INV-H-003, INV-L-001, INV-L-002, INV-L-004 |
| `test_execute_defer_against_existing_scenario_does_not_require_negotiation_id_or_mutate` | INV-L-003, INV-L-004 |
| `test_execute_send_message_against_existing_open_scenario_appends_message` | INV-H-001, INV-H-003, INV-L-001, INV-L-002, INV-L-004, INV-N-004 |
| `test_llm_decision_json_schema_describes_supported_actions` | INV-L-005 |
| `test_context_only_package_outputs_provider_neutral_prompt_without_execution` | INV-L-005 |
| `test_openai_adapter_builds_schema_constrained_responses_request` | INV-L-006 |
| `test_openai_adapter_parses_schema_constrained_decision_text` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_message_decision` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_reject_decision` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_propose_match_decision` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_accept_match_decision` | INV-L-006 |
| `test_openai_adapter_requires_api_key` | INV-L-006 |
