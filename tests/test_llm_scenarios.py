from __future__ import annotations

from pathlib import Path

from tests.support.llm_scenarios import seed_inbound_request_scenario


def test_inbound_request_scenario_produces_observable_decision_context(tmp_path: Path) -> None:
    """Protects INV-G-001, INV-N-002, INV-H-001, and INV-H-004."""
    scenario = seed_inbound_request_scenario(f"sqlite+pysqlite:///{tmp_path / 'network.db'}")

    assert scenario.observing_agent_id == "agent_2"
    assert scenario.requesting_agent_id == "agent_1"
    assert scenario.negotiation_id == "negotiation_inbound_request"
    assert scenario.decision_context["agent_id"] == "agent_2"
    assert scenario.decision_context["active_load"] == 1
    assert scenario.decision_context["inbound_requested_negotiations"] == [
        {
            "id": "negotiation_inbound_request",
            "from_agent_id": "agent_1",
            "to_agent_id": "agent_2",
            "state": "requested",
            "subject": {"role": "engineer", "location": "remote"},
        }
    ]
    assert scenario.decision_context["open_negotiations"] == []
    assert [event["type"] for event in scenario.decision_context["recent_events"]] == [
        "open_negotiation_request"
    ]
