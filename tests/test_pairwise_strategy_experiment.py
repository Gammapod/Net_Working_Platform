from __future__ import annotations

import json
from pathlib import Path

from net_working_platform.experiments.prompts import build_platform_constitution_prompt, build_representative_decision_prompt_package
from net_working_platform.experiments.scenarios import seed_pairwise_strategy_scenario, seed_viewer_showcase_scenario
from net_working_platform.experiments.strategies import get_strategy, list_strategies
from scripts.dev.run_negotiation_experiment import run_negotiation_experiment
from scripts.dev.run_unified_agent_lifecycle_experiment import _to_llm_decision_raw, _unified_turn_schema


def test_strategy_catalog_exposes_role_specific_data() -> None:
    """Exploratory strategy-catalog smoke test; invariants are protected by narrower protocol tests."""
    strategies = list_strategies()

    assert {strategy.id for strategy in strategies} == {
        "CLIENT-FAST-ANY",
        "CLIENT-INCOME-FIELD",
        "CLIENT-ADJACENT-PIVOT",
        "PRINCIPAL-CREDENTIAL-MAX",
        "PRINCIPAL-FAST-MINIMUMS",
        "PRINCIPAL-EVIDENCE-ADJACENT",
    }
    assert get_strategy("CLIENT-FAST-ANY").role == "client"
    assert get_strategy("PRINCIPAL-EVIDENCE-ADJACENT").role == "principal"
    assert get_strategy("CLIENT-FAST-ANY").to_prompt_record()["id"] == "CLIENT-FAST-ANY"


def test_platform_constitution_prompt_is_protocol_first() -> None:
    """Exploratory prompt smoke test; invariants are protected by narrower protocol tests."""
    prompt = build_platform_constitution_prompt()

    assert "choose exactly one supported protocol action" in prompt
    assert "Strategies are priorities, not permission to bypass protocol validation" in prompt
    assert "Do not invent a central platform match score" in prompt


def test_representative_decision_prompt_omits_experiment_endpoint_language() -> None:
    """Exploratory prompt smoke test; prompt policy is documented in development docs."""
    package = build_representative_decision_prompt_package(
        decision_context={
            "actor_agent_id": "agent_1",
            "represented_type": "client",
            "valid_actions": ["request_contact", "defer"],
        },
        represented_type="client",
        represented_portfolio=[{"represented_party_id": "client_1", "target_role": "backend engineer"}],
    )
    prompt = str(package["prompt"])

    assert "experiment" not in prompt.lower()
    assert "endpoint" not in prompt.lower()
    assert "prefer" not in prompt.lower()
    assert "Represent these clients" in prompt
    assert "valid_actions" in prompt


def test_pairwise_strategy_scenario_creates_open_negotiation_with_facts(tmp_path: Path) -> None:
    """Exploratory fixture smoke test; invariants are protected by narrower protocol tests."""
    scenario = seed_pairwise_strategy_scenario(
        f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}",
        client_strategy_id="CLIENT-FAST-ANY",
        principal_strategy_id="PRINCIPAL-FAST-MINIMUMS",
    )

    assert scenario.client_agent_id == "client_agent"
    assert scenario.principal_agent_id == "principal_agent"
    assert scenario.negotiation_id == "negotiation_pairwise"
    assert scenario.client_strategy_id == "CLIENT-FAST-ANY"
    assert scenario.principal_strategy_id == "PRINCIPAL-FAST-MINIMUMS"
    assert scenario.client_facts["target_field"] == "software engineering"
    assert scenario.principal_facts["role"] == "backend engineer"
    assert scenario.represented_party_profiles_by_agent["client_agent"][0].facts["salary_range"].kind == "constraint"
    assert scenario.represented_party_profiles_by_agent["principal_agent"][0].facts["employment_type"].value == ["salaried W-2"]


def test_viewer_showcase_seed_variants_include_disclosable_fact_profiles(tmp_path: Path) -> None:
    """Exploratory reusable-seed smoke test; protocol disclosure behavior is covered elsewhere."""
    scenario = seed_viewer_showcase_scenario(
        f"sqlite+pysqlite:///{tmp_path / 'viewer_showcase.db'}",
        variant="small",
    )

    assert scenario.seed_id == "viewer-showcase"
    assert scenario.seed_variant == "small"
    assert len(scenario.client_agent_ids) == 2
    assert len(scenario.principal_agent_ids) == 2
    for agent_id, profiles in scenario.represented_party_profiles_by_agent.items():
        fields = [field for profile in profiles for field in profile.facts]
        assert fields
        assert len(fields) == len(set(fields)), agent_id


def test_unified_lifecycle_schema_exposes_available_fact_fields() -> None:
    context = {
        "actor_agent_id": "agent_1",
        "field": "programming",
        "focus_negotiation_id": "negotiation_1",
        "decision_context": {
            "available_fact_disclosures_by_negotiation": {
                "negotiation_1": [
                    {"field": "client_1_target_role"},
                    {"field": "client_1_evidence"},
                ]
            }
        },
    }

    schema = _unified_turn_schema(context, ["send_message"])
    raw = _to_llm_decision_raw(
        {
            "action": "send_message",
            "actor_agent_id": "agent_1",
            "negotiation_id": "negotiation_1",
            "body": "Relevant background is available.",
            "disclose_fact_fields": ["client_1_evidence"],
        }
    )

    assert "disclose_fact_fields" in schema["required"]
    assert schema["properties"]["disclose_fact_fields"]["items"]["enum"] == ["client_1_evidence", "client_1_target_role"]
    assert raw["disclose_fact_fields"] == ["client_1_evidence"]


def test_negotiation_only_runner_writes_standard_artifacts(tmp_path: Path) -> None:
    """Exploratory standard-runner smoke test; protocol invariants are covered elsewhere."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'negotiation.db'}"
    output_dir = tmp_path / "negotiation_run"

    def fake_provider(context: dict[str, object]) -> dict[str, object]:
        actions = context["decision_context"]["valid_next_actions_by_negotiation"][context["focus_negotiation_id"]]
        action = "send_message" if "send_message" in actions else actions[0]
        base = {"action": action, "actor_agent_id": context["actor_agent_id"], "negotiation_id": context["focus_negotiation_id"]}
        if action == "send_message":
            return {**base, "body": "Sharing a concise update for the represented party.", "disclose_fact_fields": []}
        if action == "propose_match":
            return {**base, "proposal": {"summary": "Plausible fit", "details": "Continue toward a match."}, "disclose_fact_fields": []}
        if action in {"reject_negotiation", "close_negotiation"}:
            return {**base, "reason": "Continue the negotiation later."}
        return base

    summary = run_negotiation_experiment(
        db_url=db_url,
        output_dir=output_dir,
        turns=1,
        reset_db=True,
        decision_provider=fake_provider,
    )

    assert summary["runner_family"] == "negotiation-only"
    assert summary["seed_id"] == "pairwise-facts"
    assert summary["metrics"]["errors"] == 0
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "transcript.jsonl").exists()
    assert (output_dir / "graph_events.jsonl").exists()
    assert (output_dir / "initial_graph.json").exists()
    assert (output_dir / "final_graph.json").exists()


def test_negotiation_only_runner_rejects_wrong_focus_decision(tmp_path: Path) -> None:
    """Exploratory runner smoke test; focus enforcement is protected by narrower tooling tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}"
    output_dir = tmp_path / "pairwise_run"

    def wrong_actor_provider(context: dict[str, object]) -> dict[str, object]:
        return {
            "action": "send_message",
            "negotiation_id": "negotiation_pairwise",
            "actor_agent_id": "principal_agent",
            "body": "Wrong scheduled actor should not execute.",
            "disclose_fact_fields": [],
        }

    summary = run_negotiation_experiment(
        db_url=db_url,
        output_dir=output_dir,
        turns=1,
        reset_db=True,
        decision_provider=wrong_actor_provider,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["metrics"]["invalid_attempts"] == 1
    assert summary["metrics"]["focus_mismatch_attempts"] == 1
    assert summary["metrics"]["messages_sent"] == 0
    assert transcript[0]["validation"]["valid"] is False
    assert transcript[0]["validation"]["error"]["type"] == "FocusMismatch"
    assert transcript[0]["event_delta"] == []


def test_negotiation_only_runner_rejects_action_not_in_valid_next_actions(tmp_path: Path) -> None:
    """Exploratory runner smoke test; action enforcement is protected by narrower tooling tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}"
    output_dir = tmp_path / "pairwise_run"

    def invalid_accept_match_provider(context: dict[str, object]) -> dict[str, object]:
        return {
            "action": "accept_match",
            "actor_agent_id": "client_agent",
            "negotiation_id": "negotiation_pairwise",
        }

    summary = run_negotiation_experiment(
        db_url=db_url,
        output_dir=output_dir,
        turns=1,
        reset_db=True,
        decision_provider=invalid_accept_match_provider,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["metrics"]["invalid_attempts"] == 1
    assert transcript[0]["validation"]["valid"] is False
    assert transcript[0]["validation"]["error"]["type"] == "ActionUnavailable"
    assert transcript[0]["event_delta"] == []


def test_negotiation_only_runner_can_reset_existing_sqlite_database(tmp_path: Path) -> None:
    """Protects repeatable INV-H-004 experiment context generation."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}"
    first_output_dir = tmp_path / "first_pairwise_run"
    second_output_dir = tmp_path / "second_pairwise_run"

    def fake_provider(context: dict[str, object]) -> dict[str, object]:
        actions = context["decision_context"]["valid_next_actions_by_negotiation"][context["focus_negotiation_id"]]
        action = "send_message" if "send_message" in actions else actions[0]
        base = {"action": action, "negotiation_id": context["focus_negotiation_id"], "actor_agent_id": context["actor_agent_id"]}
        if action != "send_message":
            return base
        return {
            **base,
            "action": "send_message",
            "body": "Smoke test only.",
            "disclose_fact_fields": [],
        }

    run_negotiation_experiment(
        db_url=db_url,
        output_dir=first_output_dir,
        turns=1,
        reset_db=True,
        decision_provider=fake_provider,
    )
    summary = run_negotiation_experiment(
        db_url=db_url,
        output_dir=second_output_dir,
        turns=1,
        decision_provider=fake_provider,
        reset_db=True,
    )

    assert summary["reset_db"] is True
    assert summary["metrics"]["messages_sent"] == 1
