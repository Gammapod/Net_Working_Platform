from __future__ import annotations

from pathlib import Path

from scripts.dev.run_supervised_llm_experiment import run_supervised_experiment


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
