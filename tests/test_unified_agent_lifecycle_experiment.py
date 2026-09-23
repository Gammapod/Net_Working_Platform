from __future__ import annotations

import json
from pathlib import Path

from scripts.dev.run_unified_agent_lifecycle_experiment import (
    MAX_CONTACTS_PER_AGENT,
    _valid_unified_actions,
    run_unified_agent_lifecycle_experiment,
)


def test_unified_valid_actions_include_discovery_contact_and_negotiation_choices() -> None:
    context = {
        "contact_slots_remaining": 1,
        "discoverable_agents": [{"agent_id": "principal_agent", "field": "marketing"}],
        "contacts": [{"to_agent_id": "principal_agent"}],
        "negotiation_slots_remaining": 1,
        "focus_negotiation_id": "negotiation_1",
        "decision_context": {
            "valid_next_actions_by_negotiation": {
                "negotiation_1": ["send_message", "propose_match", "close_negotiation"]
            }
        },
    }

    assert _valid_unified_actions(context) == [
        "send_message",
        "propose_match",
        "close_negotiation",
    ]


def test_unified_valid_actions_hide_contact_request_at_contact_limit() -> None:
    context = {
        "contact_slots_remaining": 0,
        "discoverable_agents": [{"agent_id": "principal_agent", "field": "marketing"}],
        "contacts": [],
        "negotiation_slots_remaining": 1,
        "decision_context": {"valid_next_actions_by_negotiation": {}},
    }

    assert _valid_unified_actions(context) == ["defer"]


def test_unified_runner_uses_injected_policy_to_create_contact_and_request_negotiation(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'unified.db'}"

    def policy(context: dict[str, object]) -> dict[str, object]:
        if context["actor_agent_id"] != "marketing_client_agent_1":
            return {
                "action": "defer",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": "",
                "negotiation_id": "",
                "field": context["field"],
                "reason": "only first actor participates in this deterministic test",
                "body": "",
                "proposal": {"summary": "", "details": ""},
            }
        if context["contact_slots_remaining"] == MAX_CONTACTS_PER_AGENT:
            target = next(
                record for record in context["discoverable_agents"] if record["rationale"]["target_represented_type"] == "principal"
            )
            return {
                "action": "request_contact",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": target["agent_id"],
                "negotiation_id": "",
                "field": context["field"],
                "reason": "same-field principal",
                "body": "",
                "proposal": {"summary": "", "details": ""},
            }
        if context["contacts"]:
            return {
                "action": "request_negotiation",
                "actor_agent_id": context["actor_agent_id"],
                "target_agent_id": context["contacts"][0]["to_agent_id"],
                "negotiation_id": "",
                "field": context["field"],
                "reason": "open a same-field opportunity discussion",
                "body": "",
                "proposal": {"summary": "", "details": ""},
            }
        return {
            "action": "defer",
            "actor_agent_id": context["actor_agent_id"],
            "target_agent_id": "",
            "negotiation_id": "",
            "field": context["field"],
            "reason": "nothing useful",
            "body": "",
            "proposal": {"summary": "", "details": ""},
        }

    summary = run_unified_agent_lifecycle_experiment(
        db_url=db_url,
        output_dir=tmp_path / "run",
        turns=11,
        reset_db=True,
        decision_provider=policy,
    )

    assert summary["metrics"]["contacts_created"] == 1
    assert summary["metrics"]["negotiations_created"] == 1
    assert summary["metrics"]["decisions_by_action"] == {"defer": 9, "request_contact": 1, "request_negotiation": 1}
    assert summary["outputs"]["graph_events"] == str(tmp_path / "run" / "graph_events.jsonl")
    graph_events = [json.loads(line) for line in (tmp_path / "run" / "graph_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(graph_events) == 11
    assert graph_events[0]["raw_decision"]["action"] == "request_contact"
    assert graph_events[0]["graph_delta"]["edges_added"][0]["id"].startswith("agent_connection:")
    assert graph_events[10]["raw_decision"]["action"] == "request_negotiation"
    assert any(edge["kind"] == "negotiation" for edge in graph_events[10]["graph_delta"]["edges_added"])
