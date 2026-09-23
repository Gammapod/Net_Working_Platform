# Experiment/Test Boundary Audit

Date: 2026-09-22

This audit classifies the current experiment-adjacent tests against the ownership rule in `docs/ownership/area-ownership.md`:

- `tests/` protects deterministic platform/protocol behavior and deterministic tooling mechanics.
- `experiments/` explores product outcomes and guides protocol development.
- Tests should not protect specific experiment scenario outcomes or platform-preferred market results.

## Classification Key

- **Keep as test**: protects deterministic protocol behavior or tooling mechanics.
- **Reframe**: can remain in `tests/` if rewritten to assert generic tooling/contract behavior rather than specific scenario content or outcomes.
- **Move out of tests**: primarily documents or protects a specific experiment scenario or product outcome; should become experiment documentation, scenario catalog data, or an unprotected manual smoke script.

## Findings

### Keep As Test

These tests currently align with the boundary because they protect deterministic contracts or runner safeguards:

- `test_bandwidth_sweep_aggregate_groups_runs_by_limits`
  - Tests deterministic aggregation logic.
- `test_discovery_decision_contract.py` tests
  - Tests parsing, schema constraints, and execution through services.
- `test_supervised_llm_accept_experiment_validates_executes_and_records_event`
  - Tests validated execution and event append behavior, not model quality.
- `test_context_only_package_outputs_provider_neutral_prompt_without_execution`
  - Tests provider-neutral context packaging and non-execution.
- `test_execute_defer_against_existing_scenario_does_not_require_negotiation_id_or_mutate`
  - Tests non-mutating `defer` behavior.
- `test_execute_send_message_against_existing_open_scenario_appends_message`
  - Tests protocol execution via application services.
- `test_pairwise_strategy_runner_rejects_wrong_focus_decision`
  - Tests actor/focus enforcement.
- `test_pairwise_strategy_runner_rejects_action_not_in_valid_next_actions`
  - Tests context-valid action enforcement.
- `test_pairwise_strategy_runner_can_reset_existing_sqlite_database`
  - Tests repeatable runner setup.
- `test_scaled_experiment_runner_can_use_injected_llm_policy`
  - Tests injected-provider path and transcript capture.
- `test_scaled_experiment_runner_rejects_llm_decision_for_wrong_negotiation`
  - Tests focus enforcement before execution.
- `test_scaled_experiment_runner_can_reset_existing_sqlite_database`
  - Tests repeatable runner setup.
- `test_topic_selection_schema_requires_one_client_and_one_principal_topic`
  - Tests schema construction constraints.
- `test_topic_selection_runner_rejects_unrepresented_topic`
  - Tests deterministic validation of represented topics.
- `test_partial_topic_reject_cannot_select_principal_topic`
  - Tests validation of malformed reject output.
- `test_unified_valid_actions_include_discovery_contact_and_negotiation_choices`
  - Tests valid-action selection logic.
- `test_unified_valid_actions_hide_contact_request_at_contact_limit`
  - Tests valid-action selection logic.
- `test_weak_discovery_scenario_allows_same_field_probe_and_connection`
  - Although scenario-named, this protects weak-discovery protocol invariants through services.
- `test_weak_discovery_scenario_blocks_cross_field_probe_and_connection`
  - Although scenario-named, this protects weak-discovery protocol invariants through services.

### Reframe

These tests are valuable but currently assert specific scenario content or deterministic outcome counts more strongly than needed for invariant/tooling protection. They should be rewritten to protect generic contracts.

- `test_inbound_request_scenario_produces_observable_decision_context`
  - Reframe around "a seeded inbound-request fixture exposes structured context" rather than exact agent IDs and subject values.
- `test_referral_relay_scenario_produces_intermediary_with_two_open_negotiations`
  - Reframe around fixture validity and two open negotiations rather than named relay story details.
- `test_parallel_inbound_scenario_exposes_two_requested_negotiations`
  - Reframe around multiple inbound requests and active-load consistency rather than exact scenario IDs.
- `test_two_client_two_principal_scenario_creates_requested_starting_graph`
  - Reframe around graph snapshot structural validity rather than exact starting graph content.
- `test_strategy_catalog_exposes_role_specific_data`
  - Reframe around strategy catalog schema/role separation rather than exact catalog membership.
- `test_pairwise_strategy_scenario_creates_open_negotiation_with_facts`
  - Reframe around seed fixture structural validity and represented-party fact exposure rather than specific strategy/fact values.
- `test_pairwise_strategy_runner_writes_transcript_summary_and_strategy_metadata`
  - Keep artifact and metadata checks; reduce exact strategy-specific and outcome-specific assertions.
- `test_scaled_experiment_runner_writes_graphs_transcript_and_summary`
  - Keep artifact-writing and protocol-valid transcript checks; reduce exact final graph/outcome assertions.
- `test_scaled_experiment_runner_can_limit_turns`
  - Keep turn-limit mechanics; avoid asserting exact deterministic action sequence unless that sequence is a runner fixture, not a product outcome.
- `test_networking_runner_ends_agent_workflow_at_negotiation_request`
  - Keep workflow endpoint mechanics; reduce exact defer/action distribution assertions.
- `test_topic_selection_runner_opens_negotiation_with_exact_topic_pair`
  - Keep validation that one client and one principal topic are persisted; avoid protecting a particular "best" pair.
- `test_topic_selection_runner_can_use_ambiguous_scenario_kind`
  - Keep scenario-kind selection mechanics; avoid protecting a selected ambiguous pair as an expected outcome.
- `test_partial_topic_proposal_accepts_by_filling_principal_topic`
  - Keep two-phase accept mechanics; avoid protecting a specific client/principal topic as the desired outcome.
- `test_partial_topic_proposal_can_be_rejected_without_opening_negotiation`
  - Keep rejection-without-negotiation mechanics; avoid scenario-specific business rationale.
- `test_unified_runner_uses_injected_policy_to_create_contact_and_request_negotiation`
  - Keep contact/request mechanics; reduce exact action distribution assertions.
- `test_existing_agent_context_package_describes_open_negotiation_history`
  - Reframe around context package shape and event-history exposure rather than exact named scenario.
- `test_fit_context_package_describes_request_subject_and_fit_criteria`
  - Keep if treated as context-shape coverage; avoid implying platform-owned fit judgment.
- `test_fit_context_package_can_describe_bad_fit_request`
  - Keep only as context-shape coverage; avoid naming the request as objectively bad fit in test expectations.
- `test_fit_context_package_can_describe_ambiguous_fit_request`
  - Keep only as context-shape coverage; avoid platform-owned ambiguity judgment.
- `test_supervised_experiment_runner_outputs_database_backed_structured_event_log`
  - Keep event-log and execution checks; reduce exact scenario payload coupling where possible.
- `test_execute_decision_against_existing_scenario_reuses_prepared_database`
  - Keep prepared-database reuse mechanics; reduce exact named scenario coupling.

### Move Out Of Tests Or Convert To Scenario Catalog Documentation

No test must be immediately removed before replacement, but the following assertions are the clearest candidates to move into experiment documentation or scenario catalog entries rather than invariant tests:

- Exact strategy catalog membership in `test_strategy_catalog_exposes_role_specific_data`.
- Exact market-level outcome counts in `test_scaled_experiment_runner_observes_20_client_10_principal_market_for_10_rounds`, especially messages/proposals/deferrals/final states.
- Exact seeded topic IDs and scenario IDs in ambiguous topic-selection and partial-topic tests.
- Exact seeded graph contents in `test_two_client_two_principal_scenario_creates_requested_starting_graph`.

## Recommended Refactor Sequence

1. Maintain `docs/development/experiment-scenario-catalog.md` as the scenario catalog for current named scenarios, strategy IDs, topic IDs, and intended exploratory purpose.
2. Reframe scenario-specific tests into generic fixture/tooling tests:
   - scenario builders create structurally valid graphs;
   - generated contexts are JSON-friendly;
   - runners write transcript/summary artifacts;
   - injected decisions are validated through application services;
   - invalid focus/action/topic choices are rejected.
3. Remove invariant docstrings from tests that only protect experiment fixture shape. If a test remains, make its invariant claim about deterministic tooling or context exposure, not experiment outcome.
4. Update `docs/source-of-truth/functional-invariants.md` traceability only after tests are reframed.
5. Consider package layout changes after the audit-driven test cleanup, so file moves do not obscure behavioral intent.

## Immediate Conclusion

The current experiment-adjacent tests are mostly deterministic and useful, but several are over-coupled to named scenarios and exact outcome counts. The cleanup should prefer reframing over deletion: preserve safety checks for tooling and protocol enforcement, while moving scenario content and product-learning expectations into experiment documentation.

## Cleanup Status

Initial traceability cleanup has started:

- Exploratory experiment and scenario tests no longer claim invariant coverage in test docstrings.
- `docs/source-of-truth/functional-invariants.md` no longer maps exploratory experiment/scenario tests to invariant IDs.
- Narrow turn-guard tests now protect the runner-independent safety checks that globally valid LLM decisions must still match the scheduled actor, focus negotiation, and context-valid action before execution.

Remaining work:

- Reframe or relocate tests that still assert exact scenario contents or market outcome counts.
- Keep `docs/development/experiment-scenario-catalog.md` current as strategy IDs, seeded topic IDs, named scenarios, and intended exploratory purposes change.
- Consider moving runner guard functions out of `scripts/dev/run_pairwise_strategy_experiment.py` into a shared application or experiment-tooling module if more runners need the same checks.
