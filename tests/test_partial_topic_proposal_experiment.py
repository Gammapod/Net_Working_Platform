from __future__ import annotations

from pathlib import Path

from scripts.dev.run_partial_topic_proposal_experiment import run_partial_topic_proposal_experiment


def test_partial_topic_proposal_accepts_by_filling_principal_topic(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'partial.db'}"

    def policy(context: dict[str, object], phase: str) -> dict[str, object]:
        if phase == "proposal":
            return {
                "action": "propose_client_topic",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": context["contact_agent_id"],
                "client_topic_id": "client_data_pipeline_engineer",
                "reason": "This candidate is likely relevant to the contact's portfolio.",
            }
        return {
            "action": "accept_with_principal_topic",
            "actor_agent_id": context["actor_agent_id"],
            "requesting_agent_id": context["requesting_agent_id"],
            "principal_topic_id": "principal_data_platform_role",
            "reason": "Best represented opening for the proposed data candidate.",
        }

    summary = run_partial_topic_proposal_experiment(
        db_url=db_url,
        output_dir=tmp_path / "run",
        reset_db=True,
        decision_provider=policy,
    )

    assert summary["metrics"]["accepted"] is True
    assert summary["metrics"]["negotiations_requested"] == 1
    assert summary["metrics"]["selected_client_topic_id"] == "client_data_pipeline_engineer"
    assert summary["metrics"]["selected_principal_topic_id"] == "principal_data_platform_role"
    assert summary["execution"]["subject"]["topic_type"] == "client_topic_filled_by_responder"


def test_partial_topic_proposal_can_be_rejected_without_opening_negotiation(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'partial_reject.db'}"

    def policy(context: dict[str, object], phase: str) -> dict[str, object]:
        if phase == "proposal":
            return {
                "action": "propose_client_topic",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": context["contact_agent_id"],
                "client_topic_id": "client_backend_api_engineer",
                "reason": "Try the backend candidate.",
            }
        return {
            "action": "reject_client_topic",
            "actor_agent_id": context["actor_agent_id"],
            "requesting_agent_id": context["requesting_agent_id"],
            "principal_topic_id": "",
            "reason": "No represented opening is appropriate.",
        }

    summary = run_partial_topic_proposal_experiment(
        db_url=db_url,
        output_dir=tmp_path / "run",
        reset_db=True,
        decision_provider=policy,
    )

    assert summary["metrics"]["accepted"] is False
    assert summary["metrics"]["negotiations_requested"] == 0
    assert summary["metrics"]["open_negotiation_request_events"] == 0


def test_partial_topic_reject_cannot_select_principal_topic(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'bad_reject.db'}"

    def policy(context: dict[str, object], phase: str) -> dict[str, object]:
        if phase == "proposal":
            return {
                "action": "propose_client_topic",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": context["contact_agent_id"],
                "client_topic_id": "client_backend_api_engineer",
                "reason": "Try the backend candidate.",
            }
        return {
            "action": "reject_client_topic",
            "actor_agent_id": context["actor_agent_id"],
            "requesting_agent_id": context["requesting_agent_id"],
            "principal_topic_id": "principal_platform_api_role",
            "reason": "Malformed reject.",
        }

    try:
        run_partial_topic_proposal_experiment(
            db_url=db_url,
            output_dir=tmp_path / "run",
            reset_db=True,
            decision_provider=policy,
        )
    except ValueError as exc:
        assert "must not select a principal topic" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected malformed reject to fail")


def test_partial_topic_bad_fit_scenario_can_reject_without_negotiation(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'bad_fit.db'}"

    def policy(context: dict[str, object], phase: str) -> dict[str, object]:
        if phase == "proposal":
            assert context["scenario_id"] == "bad_fit_rejection"
            return {
                "action": "propose_client_topic",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": context["contact_agent_id"],
                "client_topic_id": "client_barista",
                "reason": "Try a hospitality candidate.",
            }
        assert context["scenario_id"] == "bad_fit_rejection"
        return {
            "action": "reject_client_topic",
            "actor_agent_id": context["actor_agent_id"],
            "requesting_agent_id": context["requesting_agent_id"],
            "principal_topic_id": "",
            "reason": "Hospitality background does not fit senior ML or security architect openings.",
        }

    summary = run_partial_topic_proposal_experiment(
        db_url=db_url,
        output_dir=tmp_path / "run",
        reset_db=True,
        scenario_kind="bad-fit",
        decision_provider=policy,
    )

    assert summary["scenario_id"] == "bad_fit_rejection"
    assert summary["metrics"]["accepted"] is False
    assert summary["metrics"]["negotiations_requested"] == 0
