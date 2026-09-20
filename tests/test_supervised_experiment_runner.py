from __future__ import annotations

from pathlib import Path

from scripts.dev.run_supervised_llm_experiment import (
    build_context_package,
    execute_decision_against_existing_scenario,
    run_supervised_experiment,
)


def test_context_only_package_outputs_provider_neutral_prompt_without_execution(tmp_path: Path) -> None:
    """Protects INV-H-004, INV-L-001, and INV-L-002."""
    result = build_context_package(db_url=f"sqlite+pysqlite:///{tmp_path / 'network.db'}")

    assert result["mode"] == "context_only"
    assert result["scenario"]["name"] == "inbound_request"
    assert result["contract"] == {
        "path": "docs/source-of-truth/llm-decision-contract.md",
        "executor_supported_actions": ["accept_negotiation", "reject_negotiation", "defer"],
    }
    assert result["response_format"] == {
        "type": "json_schema",
        "json_schema": result["llm_decision_json_schema"],
    }
    assert result["llm_decision_json_schema"]["oneOf"]
    assert result["decision_context"]["agent_id"] == "agent_2"
    assert result["decision_context"]["active_load"] == 1
    assert result["decision_context"]["max_active_negotiations"] == 5
    assert result["decision_context"]["capacity_remaining"] == 4
    assert result["prompt"].startswith("You are acting as the representative agent")
    assert "Return only one JSON object" in result["prompt"]
    assert result["event_log_source"] == "protocol_events"
    assert [event["type"] for event in result["structured_event_log"]] == ["open_negotiation_request"]
    assert "execution" not in result


def test_supervised_experiment_runner_outputs_database_backed_structured_event_log(tmp_path: Path) -> None:
    """Protects INV-H-001, INV-H-003, INV-L-001, INV-L-002, and INV-L-004."""
    result = run_supervised_experiment(
        db_url=f"sqlite+pysqlite:///{tmp_path / 'network.db'}",
        raw_decision={
            "action": "accept_negotiation",
            "negotiation_id": "negotiation_inbound_request",
            "actor_agent_id": "agent_2",
        },
    )

    assert result["scenario"]["name"] == "inbound_request"
    assert result["validation"] == {"valid": True, "action": "accept_negotiation"}
    assert result["execution"]["executed"] is True
    assert result["event_log_source"] == "protocol_events"
    assert result["structured_event_log"] == [
        {
            "type": "open_negotiation_request",
            "actor_agent_id": "agent_1",
            "negotiation_id": "negotiation_inbound_request",
            "occurred_at": "2026-01-08T12:00:00+00:00",
            "payload": {
                "to_agent_id": "agent_2",
                "subject": {"role": "engineer", "location": "remote"},
            },
        },
        {
            "type": "open_negotiation_response",
            "actor_agent_id": "agent_2",
            "negotiation_id": "negotiation_inbound_request",
            "occurred_at": "2026-01-08T12:05:00+00:00",
            "payload": {"decision": "accept"},
        },
    ]


def test_execute_decision_against_existing_scenario_reuses_prepared_database(tmp_path: Path) -> None:
    """Protects INV-H-001, INV-H-003, INV-L-001, INV-L-002, and INV-L-004."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"
    context_package = build_context_package(db_url=db_url)

    result = execute_decision_against_existing_scenario(
        db_url=db_url,
        raw_decision={
            "action": "accept_negotiation",
            "negotiation_id": context_package["scenario"]["negotiation_id"],
            "actor_agent_id": context_package["scenario"]["observing_agent_id"],
        },
    )

    assert result["scenario"] == context_package["scenario"]
    assert result["execution"]["executed"] is True
    assert [event["type"] for event in result["structured_event_log"]] == [
        "open_negotiation_request",
        "open_negotiation_response",
    ]


def test_execute_defer_against_existing_scenario_does_not_require_negotiation_id_or_mutate(
    tmp_path: Path,
) -> None:
    """Protects INV-L-003 and INV-L-004."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"
    context_package = build_context_package(db_url=db_url)

    result = execute_decision_against_existing_scenario(
        db_url=db_url,
        raw_decision={
            "action": "defer",
            "actor_agent_id": context_package["scenario"]["observing_agent_id"],
            "reason": "needs_more_information",
        },
    )

    assert result["scenario"] == context_package["scenario"]
    assert result["execution"] == {
        "executed": False,
        "action": "defer",
        "actor_agent_id": "agent_2",
        "reason": "needs_more_information",
    }
    assert [event["type"] for event in result["structured_event_log"]] == ["open_negotiation_request"]
