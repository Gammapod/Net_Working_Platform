from __future__ import annotations

import json
from pathlib import Path

from net_working_platform.experiments.prompts import build_platform_constitution_prompt, build_representative_decision_prompt_package
from net_working_platform.experiments.scenarios import seed_pairwise_strategy_scenario
from net_working_platform.experiments.strategies import get_strategy, list_strategies
from scripts.dev.run_pairwise_strategy_experiment import run_pairwise_strategy_experiment


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


def test_pairwise_strategy_runner_writes_transcript_summary_and_strategy_metadata(tmp_path: Path) -> None:
    """Exploratory runner smoke test; invariants are protected by narrower tooling tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}"
    output_dir = tmp_path / "pairwise_run"
    prompts: list[str] = []

    def fake_provider(prompt: str) -> dict[str, object]:
        prompts.append(prompt)
        assert "Platform constitution" in prompt
        assert "CLIENT-FAST-ANY" in prompt
        assert "PRINCIPAL-FAST-MINIMUMS" in prompt
        return {
            "action": "send_message",
            "negotiation_id": "negotiation_pairwise",
            "actor_agent_id": "client_agent",
            "body": "Client can start quickly and meets the backend minimums.",
        }

    summary = run_pairwise_strategy_experiment(
        db_url=db_url,
        output_dir=output_dir,
        client_strategy_id="CLIENT-FAST-ANY",
        principal_strategy_id="PRINCIPAL-FAST-MINIMUMS",
        turns=1,
        decision_source="injected_llm",
        decision_provider=fake_provider,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    written_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary == written_summary
    assert len(prompts) == 1
    assert summary["baseline_model"] == "gpt-4o-mini"
    assert summary["client_strategy"]["id"] == "CLIENT-FAST-ANY"
    assert summary["principal_strategy"]["id"] == "PRINCIPAL-FAST-MINIMUMS"
    assert summary["metrics"]["messages_sent"] == 1
    assert summary["metrics"]["invalid_attempts"] == 0
    assert transcript[0]["scheduled_actor_agent_id"] == "client_agent"
    assert transcript[0]["strategy"]["id"] == "CLIENT-FAST-ANY"
    assert transcript[0]["event_delta"][0]["type"] == "message"
    assert transcript[0]["skipped"] is False


def test_pairwise_strategy_runner_rejects_wrong_focus_decision(tmp_path: Path) -> None:
    """Exploratory runner smoke test; focus enforcement is protected by narrower tooling tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}"
    output_dir = tmp_path / "pairwise_run"

    def wrong_actor_provider(prompt: str) -> dict[str, object]:
        return {
            "action": "send_message",
            "negotiation_id": "negotiation_pairwise",
            "actor_agent_id": "principal_agent",
            "body": "Wrong scheduled actor should not execute.",
        }

    summary = run_pairwise_strategy_experiment(
        db_url=db_url,
        output_dir=output_dir,
        client_strategy_id="CLIENT-FAST-ANY",
        principal_strategy_id="PRINCIPAL-FAST-MINIMUMS",
        turns=1,
        decision_source="injected_llm",
        decision_provider=wrong_actor_provider,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["metrics"]["invalid_attempts"] == 1
    assert summary["metrics"]["focus_mismatch_attempts"] == 1
    assert summary["metrics"]["messages_sent"] == 0
    assert transcript[0]["validation"]["valid"] is False
    assert transcript[0]["validation"]["error"]["type"] == "FocusMismatch"
    assert transcript[0]["event_delta"] == []


def test_pairwise_strategy_runner_rejects_action_not_in_valid_next_actions(tmp_path: Path) -> None:
    """Exploratory runner smoke test; action enforcement is protected by narrower tooling tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}"
    output_dir = tmp_path / "pairwise_run"

    def invalid_defer_provider(prompt: str) -> dict[str, object]:
        return {
            "action": "defer",
            "actor_agent_id": "client_agent",
            "reason": "Should not be valid while negotiation actions are available.",
        }

    summary = run_pairwise_strategy_experiment(
        db_url=db_url,
        output_dir=output_dir,
        client_strategy_id="CLIENT-FAST-ANY",
        principal_strategy_id="PRINCIPAL-FAST-MINIMUMS",
        turns=1,
        decision_source="injected_llm",
        decision_provider=invalid_defer_provider,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["metrics"]["invalid_attempts"] == 1
    assert transcript[0]["validation"]["valid"] is False
    assert transcript[0]["validation"]["error"]["type"] == "ActionUnavailable"
    assert transcript[0]["event_delta"] == []


def test_pairwise_strategy_runner_can_reset_existing_sqlite_database(tmp_path: Path) -> None:
    """Protects repeatable INV-H-004 experiment context generation."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'pairwise.db'}"
    first_output_dir = tmp_path / "first_pairwise_run"
    second_output_dir = tmp_path / "second_pairwise_run"

    def fake_provider(prompt: str) -> dict[str, object]:
        return {
            "action": "send_message",
            "negotiation_id": "negotiation_pairwise",
            "actor_agent_id": "client_agent",
            "body": "Smoke test only.",
        }

    run_pairwise_strategy_experiment(
        db_url=db_url,
        output_dir=first_output_dir,
        client_strategy_id="CLIENT-FAST-ANY",
        principal_strategy_id="PRINCIPAL-FAST-MINIMUMS",
        turns=1,
        decision_source="injected_llm",
        decision_provider=fake_provider,
    )
    summary = run_pairwise_strategy_experiment(
        db_url=db_url,
        output_dir=second_output_dir,
        client_strategy_id="CLIENT-FAST-ANY",
        principal_strategy_id="PRINCIPAL-FAST-MINIMUMS",
        turns=1,
        decision_source="injected_llm",
        decision_provider=fake_provider,
        reset_db=True,
    )

    assert summary["reset_db"] is True
    assert summary["metrics"]["messages_sent"] == 1
