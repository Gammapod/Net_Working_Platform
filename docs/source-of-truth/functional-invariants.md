# Functional Invariants

This is the source of truth for MVP protocol behavior. Every automated test that protects product behavior should reference one or more invariant IDs from this document.

## Scope

The MVP is a graph-backed communication platform for representative agents. Agents represent clients and principals, discover same-field weak agent opportunities, form active agent-agent edges, and run structured negotiations over established agent-agent connections.

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

- `test_client_and_principal_node_types_are_distinct`
- `test_core_table_columns_match_repository_contracts`

### INV-E-003: Representation Edges Are Not Agent-Agent Edges

An agent-client or agent-principal representation edge is a different relationship type from an agent-agent communication edge.

Protected by:

- `test_representation_edges_are_separate_from_agent_connections`
- `test_sql_repositories_round_trip_core_graph_records`

## Edge Invariants

### INV-G-001: Agent-Agent Communication Requires An Active Edge

An agent may request a negotiation with another agent only when there is an active agent-agent edge between them.

Protected by:

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

## Discovery Invariants

### INV-D-001: Weak Discovery Is Field-Scoped

Weak discovery edges expose limited agent-agent discoverability by field. An agent may list or probe only currently available weak discovery edges from itself to another agent in the requested field. Weak discovery does not expose unrelated fields and does not by itself authorize negotiation.

Protected by:

- `test_list_discoverable_agents_filters_weak_edges_by_field`
- `test_probe_weak_connection_requires_matching_weak_edge`

### INV-D-002: Weak Discovery Gates New Contacts

An agent may form a new active directional contact from weak discovery only when a matching available weak discovery edge exists. Cross-field contact attempts without a weak edge are rejected and must not create active agent-agent communication edges.

Protected by:

- `test_probe_weak_connection_requires_matching_weak_edge`
- `test_request_contact_requires_matching_weak_edge_and_creates_active_connection`

### INV-D-003: Active Contacts Are Limited

An agent may keep at most three active outgoing contacts. The contact is directional; another agent must independently add, ignore, or eventually block/mark low-confidence.

Protected by:

- `test_request_contact_rejects_actor_over_contact_limit`

## Negotiation Protocol Invariants

### INV-N-001: Negotiations Are First-Class Records

A negotiation is its own record. It is not only an edge state or a message thread.

Protected by:

- `test_open_negotiation_request_creates_requested_state`
- `test_request_negotiation_service_creates_record_and_event`
- `test_sql_repositories_round_trip_negotiation_and_events_in_order`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-002: Negotiation Starts Requested

An `open_negotiation_request` creates a negotiation in `requested` state.

Protected by:

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

Free-form negotiation messages are valid only while the negotiation is `open` or `proposal_pending`. A message in `proposal_pending` returns the negotiation to `open`.

Protected by:

- `test_message_keeps_open_negotiation_open`
- `test_message_reopens_proposal_pending_negotiation`
- `test_message_requires_open_negotiation`
- `test_send_message_service_appends_message_event_for_open_negotiation`
- `test_send_message_service_reopens_proposal_pending_negotiation`
- `test_send_message_service_rejects_non_open_negotiation`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-005: Match Acceptance Requires Match Proposal

`match_accepted` is valid only while a negotiation is in `proposal_pending` after a match proposal.

Protected by:

- `test_match_proposal_moves_negotiation_to_proposal_pending`
- `test_match_acceptance_requires_prior_proposal`
- `test_match_acceptance_closes_as_matched_after_proposal`
- `test_propose_match_service_appends_event_for_open_negotiation`
- `test_accept_match_service_requires_prior_proposal`
- `test_accept_match_service_marks_negotiation_matched`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-N-009: Pending Match Proposals Require Resolution Or Continued Negotiation

`propose_match` moves an `open` negotiation to `proposal_pending`. While a proposal is pending, another proposal may not be made. Valid responses are `accept_match`, `close_negotiation`, or `send_message` when the actor has message budget remaining. A message returns the negotiation to `open`; acceptance moves it to `matched`; closure moves it to `closed`.

Protected by:

- `test_match_proposal_moves_negotiation_to_proposal_pending`
- `test_message_reopens_proposal_pending_negotiation`
- `test_proposal_pending_rejects_additional_match_proposal`
- `test_propose_match_service_appends_event_for_open_negotiation`
- `test_accept_match_service_requires_prior_proposal`
- `test_accept_match_service_marks_negotiation_matched`
- `test_send_message_service_reopens_proposal_pending_negotiation`
- `test_get_agent_decision_context_includes_accept_match_after_match_proposal`
- `test_get_agent_decision_context_forces_accept_or_close_after_proposal_when_quota_used`

### INV-N-006: Matched And Closed Are Terminal

No protocol action may reopen or mutate a negotiation after it reaches `matched` or `closed`, except append-only audit/read-model events that do not change status.

Protected by:

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

### INV-N-008: Free-Form Messages Are Bandwidth-Limited

Free-form `send_message` actions are limited to three messages per actor per negotiation. Once an actor has sent three free-form messages in a negotiation, that actor may not send another message in that negotiation. Other protocol actions remain available according to negotiation state. If a match proposal is pending and the actor has no message bandwidth remaining, the actor's valid next actions are limited to accepting the match or closing the negotiation.

Protected by:

- `test_send_message_service_rejects_message_after_actor_quota_used`
- `test_message_quota_is_per_actor_per_negotiation`
- `test_get_agent_decision_context_excludes_send_message_when_quota_used`
- `test_get_agent_decision_context_forces_accept_or_close_after_proposal_when_quota_used`

## Event And History Invariants

### INV-H-001: Every Protocol Action Appends An Event

Every protocol action must create an append-only event with actor, timestamp, negotiation or edge reference, type, and payload.

Protected by:

- `test_request_negotiation_service_creates_record_and_event`
- `test_accept_negotiation_service_opens_requested_negotiation`
- `test_reject_negotiation_service_closes_requested_negotiation`
- `test_send_message_service_appends_message_event_for_open_negotiation`
- `test_propose_match_service_appends_event_for_open_negotiation`
- `test_accept_match_service_marks_negotiation_matched`
- `test_close_negotiation_service_closes_open_negotiation`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

## Represented-Party Fact Invariants

### INV-F-001: Represented-Party Facts Are Disclosed Structurally

Agents may attach zero or more known represented-party fact fields to a substantive negotiation action. Fact disclosure is not a standalone protocol action. Each disclosed fact must reference an existing currently available represented-party field for the actor, preserve the field kind and value, and append a `fact_disclosed` event before the attached substantive action event.

Protected by:

- `test_disclose_facts_appends_structured_fact_events`
- `test_disclose_fact_rejects_unknown_or_unrepresented_field`
- `test_agent_decision_context_exposes_available_and_disclosed_facts`
- `test_execute_llm_decision_discloses_attached_facts_before_protocol_action`

### INV-F-002: Fact Disclosure Does Not Consume Message Budget

Structured fact disclosure is not a free-form message and must not count against the actor's per-negotiation `send_message` quota, even when attached to a `send_message` action.

Protected by:

- `test_fact_disclosure_does_not_consume_message_budget`

### INV-F-003: Fact Fields Are Disclosed At Most Once Per Negotiation

A represented-party fact field may be disclosed at most once per negotiation by the representing agent.

Protected by:

- `test_fact_field_is_disclosed_at_most_once_per_negotiation`

### INV-H-002: Event History Is Append-Only

Existing events must not be updated or deleted through application services.

Protected by:

- Planned: `test_events_are_append_only`

### INV-H-003: Retrieval APIs Return Structured History

History retrieval must return structured records, not only concatenated text.

Protected by:

- `test_retrieve_negotiation_history_returns_structured_events`
- `test_sql_repositories_round_trip_negotiation_and_events_in_order`
- `test_sql_backed_negotiation_service_runs_full_lifecycle`

### INV-H-004: Agent Decision Context Is Structured And Read-Only

Agent decision context retrieval must return structured, JSON-friendly data for a single agent without mutating negotiations or appending protocol events. The context must include active load, capacity information when supplied, inbound requested negotiations, open negotiations, recent protocol events relevant to that agent, the full supported protocol action list, message budget information by active negotiation, and valid next actions by active negotiation state.

Protected by:

- `test_get_agent_decision_context_returns_structured_read_only_context`
- `test_cli_returns_agent_decision_context`
- `test_get_agent_decision_context_includes_capacity_when_limit_supplied`
- `test_get_agent_decision_context_excludes_send_message_when_quota_used`

### INV-H-005: Graph Snapshots Are Structured And Read-Only

Graph snapshot retrieval must return structured, viewer-ready, JSON-friendly data without mutating graph, negotiation, or protocol-event state. Snapshots must include nodes and relationship edges with short labels plus richer details for inspection. Negotiations may appear as protocol overlay edges.

Protected by:

- `test_build_graph_snapshot_returns_viewer_ready_nodes_and_edges`
- `test_sql_graph_snapshot_reader_reads_current_graph_state`
- `test_cli_returns_graph_snapshot`
- `test_render_graph_snapshot_mermaid_uses_short_labels_and_edge_styles`
- `test_cli_returns_graph_mermaid`
- `test_graph_evolution_demo_writes_before_after_graphs`

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

The LLM decision contract must expose machine-readable JSON Schema so providers that support structured output can be constrained by schema instead of prose alone. Experiment runners may derive stricter turn-specific schemas from valid next actions, scheduled actor, and focus negotiation.

Protected by:

- `test_llm_decision_json_schema_describes_supported_actions`
- `test_turn_decision_json_schema_constrains_actions_actor_and_negotiation`
- `test_context_only_package_outputs_provider_neutral_prompt_without_execution`

### INV-L-006: Dev Provider Adapters Use Schema-Constrained Output

Dev-only provider adapters must use the LLM decision JSON Schema, or a stricter turn-specific schema, as the provider output constraint when the provider supports schema-constrained responses. Provider credentials must be read from environment variables, not stored in repository files.

Protected by:

- `test_openai_adapter_builds_schema_constrained_responses_request`
- `test_openai_adapter_accepts_turn_specific_schema_override`
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
- `test_llm_turn_guard_rejects_wrong_actor_focus_before_execution`
- `test_llm_turn_guard_rejects_wrong_negotiation_focus_before_execution`
- `test_llm_turn_guard_rejects_action_unavailable_in_context`

## Capacity Invariants

### INV-C-001: Open Negotiation Limit Is Enforced

An agent cannot exceed its configured maximum active negotiations. Active load includes `requested`, `open`, and `proposal_pending` negotiations where the agent is either `from_agent_id` or `to_agent_id`. `matched` and `closed` negotiations do not count as active load.

Protected by:

- `test_open_negotiation_capacity_allows_below_limit`
- `test_open_negotiation_capacity_rejects_at_limit`
- `test_request_negotiation_service_rejects_when_actor_at_capacity`
- `test_sql_negotiation_repository_counts_requested_open_and_proposal_pending_as_active_load`
- `test_sql_negotiation_repository_counts_inbound_requested_open_and_proposal_pending_as_active_load`

### INV-C-002: Capacity Rejections Are Recorded

A protocol action rejected due to capacity must append an event explaining the rejection.

Protected by:

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

## Experiment Tooling Invariants

### INV-X-001: Experiment Runs Emit Standard Inspectable Artifacts

Experiment runner entrypoints intended for repository users must emit a stable run folder containing versioned run metadata, the seed used for the run, structured summary data, a JSONL transcript, and structured initial/final graph snapshots. Convenience renderings such as Mermaid graphs may be emitted in addition to the structured artifacts, but they must not be the only inspectable graph output.

Protected by:

- `test_unified_experiment_runner_writes_standard_inspection_artifacts`
- `test_unified_experiment_runner_rejects_unsupported_seed_version`

### INV-X-002: Editable Graph Seeds Drive Demo Runs

Versioned experiment seeds may define a small starting graph in editable JSON, including nodes, representation edges, agent-agent connections, initial negotiations, and scripted turns. The user-facing experiment runner must validate required seed sections, import the declared graph through normal storage/application services, execute scripted turns through protocol services, and preserve the exact seed used for the run in the output folder.

Protected by:

- `test_unified_experiment_runner_imports_editable_graph_seed`

### INV-X-003: Experiment Timelines Link Turns To Graph Changes

Inspectable experiment runs must emit a structured JSONL timeline artifact that can be consumed by future viewer tooling. Each timeline record must identify the turn, actor, negotiation focus when applicable, raw decision, validation result, protocol event deltas, and graph-visible node/edge changes observed for that turn when snapshots are available. The timeline artifact is an observation/export format; it must not create hidden protocol behavior or replace append-only protocol events.

Protected by:

- `test_unified_experiment_runner_writes_graph_event_timeline`

### INV-X-004: Run Viewer Exports Are Static Artifact Consumers

Run viewer exports must consume existing run artifacts without mutating protocol state, databases, seeds, transcripts, timeline files, or graph snapshots. The first viewer export may be a static HTML file, but it must embed or reference structured run data, expose initial/final graph data, expose timeline records, and provide inspectable per-turn details for future frontend refinement.

Protected by:

- `test_export_run_viewer_writes_static_html_from_run_artifacts`
- `test_export_run_viewer_can_write_custom_output_file`
- `test_export_run_viewer_reports_missing_run_artifacts`

## Test Traceability

| Test | Invariants |
| --- | --- |
| `test_domain_smoke` | INV-N-004 |
| `test_open_negotiation_request_creates_requested_state` | INV-N-001, INV-N-002 |
| `test_accept_requested_negotiation_opens` | INV-N-003 |
| `test_reject_requested_negotiation_closes` | INV-N-003 |
| `test_message_keeps_open_negotiation_open` | INV-N-004 |
| `test_message_requires_open_negotiation` | INV-N-004 |
| `test_match_proposal_moves_negotiation_to_proposal_pending` | INV-N-005, INV-N-009 |
| `test_match_acceptance_requires_prior_proposal` | INV-N-005, INV-N-009 |
| `test_match_acceptance_closes_as_matched_after_proposal` | INV-N-005, INV-N-009 |
| `test_message_reopens_proposal_pending_negotiation` | INV-N-004, INV-N-009 |
| `test_proposal_pending_rejects_additional_match_proposal` | INV-N-009 |
| `test_closed_negotiation_rejects_messages` | INV-N-006 |
| `test_matched_negotiation_rejects_close` | INV-N-006 |
| `test_agent_node_uses_agent_type` | INV-E-001 |
| `test_client_and_principal_node_types_are_distinct` | INV-E-002 |
| `test_representation_edges_are_separate_from_agent_connections` | INV-E-003 |
| `test_request_negotiation_requires_active_agent_connection` | INV-G-001 |
| `test_open_negotiation_capacity_allows_below_limit` | INV-C-001 |
| `test_open_negotiation_capacity_rejects_at_limit` | INV-C-001 |
| `test_request_negotiation_service_requires_active_connection` | INV-G-001 |
| `test_list_discoverable_agents_filters_weak_edges_by_field` | INV-D-001 |
| `test_probe_weak_connection_requires_matching_weak_edge` | INV-D-001, INV-D-002 |
| `test_request_contact_requires_matching_weak_edge_and_creates_active_connection` | INV-D-002, INV-G-001 |
| `test_request_contact_rejects_actor_over_contact_limit` | INV-D-003 |
| `test_parse_discovery_request_contact_decision` | INV-L-001, INV-L-002, INV-D-002 |
| `test_parse_discovery_decision_rejects_unknown_action` | INV-L-001 |
| `test_discovery_turn_schema_constrains_targets_and_fields` | INV-L-005, INV-L-006, INV-D-001 |
| `test_execute_discovery_decision_uses_service` | INV-L-004, INV-D-002 |
| `test_request_negotiation_service_creates_record_and_event` | INV-N-001, INV-N-002, INV-H-001 |
| `test_request_negotiation_service_rejects_when_actor_at_capacity` | INV-C-001, INV-C-002 |
| `test_accept_negotiation_service_opens_requested_negotiation` | INV-N-003, INV-H-001 |
| `test_reject_negotiation_service_closes_requested_negotiation` | INV-N-003, INV-H-001 |
| `test_send_message_service_appends_message_event_for_open_negotiation` | INV-N-004, INV-H-001 |
| `test_send_message_service_reopens_proposal_pending_negotiation` | INV-N-004, INV-N-009, INV-H-001 |
| `test_send_message_service_rejects_non_open_negotiation` | INV-N-004 |
| `test_send_message_service_rejects_message_after_actor_quota_used` | INV-N-008 |
| `test_message_quota_is_per_actor_per_negotiation` | INV-N-008 |
| `test_disclose_facts_appends_structured_fact_events` | INV-F-001 |
| `test_disclose_fact_rejects_unknown_or_unrepresented_field` | INV-F-001 |
| `test_fact_field_is_disclosed_at_most_once_per_negotiation` | INV-F-003 |
| `test_fact_disclosure_does_not_consume_message_budget` | INV-F-002, INV-N-008 |
| `test_agent_decision_context_exposes_available_and_disclosed_facts` | INV-F-001, INV-H-004 |
| `test_propose_match_service_appends_event_for_open_negotiation` | INV-N-005, INV-N-009, INV-H-001 |
| `test_accept_match_service_requires_prior_proposal` | INV-N-005, INV-N-009 |
| `test_accept_match_service_marks_negotiation_matched` | INV-N-005, INV-N-009, INV-H-001 |
| `test_close_negotiation_service_closes_open_negotiation` | INV-N-006, INV-H-001 |
| `test_retrieve_negotiation_history_returns_structured_events` | INV-H-003 |
| `test_storage_schema_declares_mvp_tables` | INV-E-001 |
| `test_agent_connections_are_directional` | INV-G-001 |
| `test_core_table_columns_match_repository_contracts` | INV-E-002 |
| `test_storage_schema_uses_check_constraints_for_domain_enums` | INV-E-001, INV-E-002, INV-N-002, INV-N-006 |
| `test_sql_repositories_round_trip_core_graph_records` | INV-E-001, INV-E-003 |
| `test_sql_negotiation_repository_counts_requested_open_and_proposal_pending_as_active_load` | INV-C-001 |
| `test_sql_negotiation_repository_counts_inbound_requested_open_and_proposal_pending_as_active_load` | INV-C-001 |
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
| `test_get_agent_decision_context_excludes_send_message_when_quota_used` | INV-H-004, INV-N-008 |
| `test_get_agent_decision_context_includes_accept_match_after_match_proposal` | INV-H-004, INV-N-009 |
| `test_get_agent_decision_context_forces_accept_or_close_after_proposal_when_quota_used` | INV-H-004, INV-N-005, INV-N-008, INV-N-009 |
| `test_cli_returns_agent_decision_context` | INV-H-004, INV-CLI-001, INV-CLI-002 |
| `test_build_graph_snapshot_returns_viewer_ready_nodes_and_edges` | INV-H-005 |
| `test_sql_graph_snapshot_reader_reads_current_graph_state` | INV-H-005 |
| `test_cli_returns_graph_snapshot` | INV-H-005, INV-CLI-001, INV-CLI-002 |
| `test_render_graph_snapshot_mermaid_uses_short_labels_and_edge_styles` | INV-H-005 |
| `test_cli_returns_graph_mermaid` | INV-H-005, INV-CLI-001, INV-CLI-002 |
| `test_graph_evolution_demo_writes_before_after_graphs` | INV-H-005 |
| `test_parse_llm_accept_negotiation_decision` | INV-L-001, INV-L-002 |
| `test_parse_llm_decision_rejects_unknown_action` | INV-L-001 |
| `test_parse_llm_decision_requires_action_specific_fields` | INV-L-002 |
| `test_parse_llm_decision_rejects_extra_fields` | INV-L-002 |
| `test_parse_llm_defer_decision` | INV-L-003 |
| `test_parse_llm_decision_accepts_attached_fact_disclosure_fields` | INV-L-001, INV-L-002 |
| `test_parse_llm_decision_rejects_invalid_attached_fact_disclosure_fields` | INV-L-002 |
| `test_execute_llm_accept_negotiation_decision_uses_service` | INV-L-004, INV-N-003, INV-H-001 |
| `test_execute_llm_reject_negotiation_decision_uses_service` | INV-L-004, INV-N-003, INV-H-001 |
| `test_execute_llm_send_message_decision_uses_service` | INV-L-004, INV-N-004, INV-H-001 |
| `test_execute_llm_propose_match_decision_uses_service` | INV-L-004, INV-N-005, INV-H-001 |
| `test_execute_llm_accept_match_decision_uses_service` | INV-L-004, INV-N-005, INV-H-001 |
| `test_execute_llm_close_negotiation_decision_uses_service` | INV-L-004, INV-N-006, INV-H-001 |
| `test_execute_llm_decision_discloses_attached_facts_before_protocol_action` | INV-L-004, INV-F-001 |
| `test_execute_llm_defer_decision_does_not_mutate_protocol_state` | INV-L-003, INV-L-004 |
| `test_llm_decision_json_schema_describes_supported_actions` | INV-L-005 |
| `test_turn_decision_json_schema_constrains_actions_actor_and_negotiation` | INV-L-005, INV-L-006 |
| `test_context_only_package_outputs_provider_neutral_prompt_without_execution` | INV-L-005 |
| `test_openai_adapter_builds_schema_constrained_responses_request` | INV-L-006 |
| `test_openai_adapter_accepts_turn_specific_schema_override` | INV-L-006 |
| `test_openai_adapter_parses_schema_constrained_decision_text` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_message_decision` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_reject_decision` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_propose_match_decision` | INV-L-006 |
| `test_openai_adapter_normalizes_schema_constrained_accept_match_decision` | INV-L-006 |
| `test_openai_adapter_requires_api_key` | INV-L-006 |
| `test_llm_turn_guard_rejects_wrong_actor_focus_before_execution` | INV-L-004 |
| `test_llm_turn_guard_rejects_wrong_negotiation_focus_before_execution` | INV-L-004 |
| `test_llm_turn_guard_rejects_action_unavailable_in_context` | INV-L-004 |
| `test_unified_experiment_runner_writes_standard_inspection_artifacts` | INV-X-001 |
| `test_unified_experiment_runner_rejects_unsupported_seed_version` | INV-X-001 |
| `test_unified_experiment_runner_imports_editable_graph_seed` | INV-X-002 |
| `test_unified_experiment_runner_writes_graph_event_timeline` | INV-X-003 |
| `test_export_run_viewer_writes_static_html_from_run_artifacts` | INV-X-004 |
| `test_export_run_viewer_can_write_custom_output_file` | INV-X-004 |
| `test_export_run_viewer_reports_missing_run_artifacts` | INV-X-004 |
