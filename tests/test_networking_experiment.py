from __future__ import annotations

from pathlib import Path

from scripts.dev.run_networking_experiment import _valid_networking_actions, run_networking_experiment


def test_networking_valid_actions_prioritize_negotiation_request_after_contact() -> None:
    context = {
        "workflow_complete": False,
        "contacts": [{"to_agent_id": "principal_agent"}],
        "negotiation_slots_remaining": 1,
        "discoverable_agents": [{"agent_id": "other_agent"}],
        "contact_slots_remaining": 2,
    }

    assert _valid_networking_actions(context) == ["request_negotiation"]


def test_networking_valid_actions_allow_contact_when_no_contact_exists() -> None:
    context = {
        "workflow_complete": False,
        "contacts": [],
        "negotiation_slots_remaining": 1,
        "discoverable_agents": [{"agent_id": "principal_agent"}],
        "contact_slots_remaining": 1,
    }

    assert _valid_networking_actions(context) == ["probe_weak_connection", "request_contact"]


def test_networking_runner_ends_agent_workflow_at_negotiation_request(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'networking.db'}"

    def policy(context: dict[str, object]) -> dict[str, object]:
        if context["actor_agent_id"] != "marketing_client_agent_1":
            return {
                "action": "defer",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": "",
                "field": context["field"],
                "reason": "not participating",
            }
        if context["contacts"]:
            return {
                "action": "request_negotiation",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": context["contacts"][0]["to_agent_id"],
                "field": context["field"],
                "reason": "open networking endpoint negotiation",
            }
        target = next(record for record in context["discoverable_agents"] if record["rationale"]["target_represented_type"] == "principal")
        return {
            "action": "request_contact",
            "actor_agent_id": context["actor_agent_id"],
            "target_agent_id": target["agent_id"],
            "field": context["field"],
            "reason": "same-field principal contact",
        }

    summary = run_networking_experiment(
        db_url=db_url,
        output_dir=tmp_path / "run",
        turns=21,
        reset_db=True,
        decision_provider=policy,
    )

    assert summary["metrics"]["contacts_created"] == 1
    assert summary["metrics"]["negotiations_requested"] == 1
    assert summary["metrics"]["workflows_completed"] == 1
    assert summary["metrics"]["decisions_by_action"] == {"defer": 18, "request_contact": 1, "request_negotiation": 1}
    assert summary["metrics"]["skipped_completed_workflows"] == 1
