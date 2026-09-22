from __future__ import annotations

from pathlib import Path

from scripts.dev.run_topic_selection_networking_experiment import (
    _topic_selection_schema,
    run_topic_selection_networking_experiment,
)
from net_working_platform.experiments.scenarios import (
    seed_ambiguous_multi_party_contact_scenario,
    seed_multi_party_contact_scenario,
)


def test_topic_selection_schema_requires_one_client_and_one_principal_topic(tmp_path: Path) -> None:
    scenario = seed_multi_party_contact_scenario(f"sqlite+pysqlite:///{tmp_path / 'schema.db'}")

    schema = _topic_selection_schema(scenario)

    assert schema["required"] == [
        "action",
        "actor_agent_id",
        "target_agent_id",
        "client_topic_id",
        "principal_topic_id",
        "reason",
    ]
    assert schema["properties"]["client_topic_id"]["enum"] == sorted(scenario.client_ids)
    assert schema["properties"]["principal_topic_id"]["enum"] == sorted(scenario.principal_ids)


def test_topic_selection_runner_opens_negotiation_with_exact_topic_pair(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'topic_selection.db'}"

    def policy(context: dict[str, object]) -> dict[str, object]:
        return {
            "action": "request_negotiation",
            "actor_agent_id": context["actor_agent_id"],
            "target_agent_id": context["contact_agent_id"],
            "client_topic_id": "client_marketing_generalist",
            "principal_topic_id": "principal_marketing_role",
            "reason": "Best field and role overlap among available topics.",
        }

    summary = run_topic_selection_networking_experiment(
        db_url=db_url,
        output_dir=tmp_path / "run",
        reset_db=True,
        decision_provider=policy,
    )

    assert summary["metrics"]["negotiations_requested"] == 1
    assert summary["metrics"]["open_negotiation_request_events"] == 1
    assert summary["metrics"]["selected_client_topic_id"] == "client_marketing_generalist"
    assert summary["metrics"]["selected_principal_topic_id"] == "principal_marketing_role"
    assert summary["metrics"]["exactly_one_client_topic"] is True
    assert summary["metrics"]["exactly_one_principal_topic"] is True
    assert summary["execution"]["subject"]["client_id"] == "client_marketing_generalist"
    assert summary["execution"]["subject"]["principal_id"] == "principal_marketing_role"


def test_topic_selection_runner_rejects_unrepresented_topic(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'bad_topic.db'}"

    def policy(context: dict[str, object]) -> dict[str, object]:
        return {
            "action": "request_negotiation",
            "actor_agent_id": context["actor_agent_id"],
            "target_agent_id": context["contact_agent_id"],
            "client_topic_id": "client_not_represented",
            "principal_topic_id": "principal_marketing_role",
            "reason": "Invalid topic should be rejected.",
        }

    try:
        run_topic_selection_networking_experiment(
            db_url=db_url,
            output_dir=tmp_path / "run",
            reset_db=True,
            decision_provider=policy,
        )
    except ValueError as exc:
        assert "not represented by the actor" in str(exc)
    else:  # pragma: no cover - explicit assertion path
        raise AssertionError("expected invalid client topic to be rejected")


def test_ambiguous_topic_selection_scenario_exposes_two_plausible_pairs(tmp_path: Path) -> None:
    scenario = seed_ambiguous_multi_party_contact_scenario(f"sqlite+pysqlite:///{tmp_path / 'ambiguous.db'}")

    assert scenario.scenario_id == "ambiguous_two_plausible_pairs"
    assert set(scenario.client_ids) == {"client_backend_api_engineer", "client_data_pipeline_engineer"}
    assert set(scenario.principal_ids) == {"principal_platform_api_role", "principal_data_platform_role"}


def test_topic_selection_runner_can_use_ambiguous_scenario_kind(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'ambiguous_runner.db'}"

    def policy(context: dict[str, object]) -> dict[str, object]:
        assert context["scenario_id"] == "ambiguous_two_plausible_pairs"
        return {
            "action": "request_negotiation",
            "actor_agent_id": context["actor_agent_id"],
            "target_agent_id": context["contact_agent_id"],
            "client_topic_id": "client_data_pipeline_engineer",
            "principal_topic_id": "principal_data_platform_role",
            "reason": "Quick-placement data pipeline fit.",
        }

    summary = run_topic_selection_networking_experiment(
        db_url=db_url,
        output_dir=tmp_path / "ambiguous-run",
        reset_db=True,
        scenario_kind="ambiguous",
        decision_provider=policy,
    )

    assert summary["scenario_kind"] == "ambiguous"
    assert summary["scenario_id"] == "ambiguous_two_plausible_pairs"
    assert summary["metrics"]["selected_client_topic_id"] == "client_data_pipeline_engineer"
    assert summary["metrics"]["selected_principal_topic_id"] == "principal_data_platform_role"
