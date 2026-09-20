from __future__ import annotations

from pathlib import Path

from tests.support.llm_scenarios import (
    seed_inbound_request_scenario,
    seed_parallel_inbound_scenario,
    seed_referral_relay_scenario,
)


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


def test_referral_relay_scenario_produces_intermediary_with_two_open_negotiations(tmp_path: Path) -> None:
    """Protects INV-G-001, INV-N-003, INV-N-004, INV-H-001, and INV-H-004."""
    scenario = seed_referral_relay_scenario(f"sqlite+pysqlite:///{tmp_path / 'network.db'}")

    assert scenario.requesting_agent_id == "agent_1"
    assert scenario.intermediary_agent_id == "agent_2"
    assert scenario.referred_agent_id == "agent_3"
    assert scenario.upstream_negotiation_id == "negotiation_agent1_agent2"
    assert scenario.downstream_negotiation_id == "negotiation_agent2_agent3"


def test_parallel_inbound_scenario_exposes_two_requested_negotiations(tmp_path: Path) -> None:
    """Protects INV-G-001, INV-N-002, INV-H-001, INV-H-004, and INV-C-001."""
    scenario = seed_parallel_inbound_scenario(f"sqlite+pysqlite:///{tmp_path / 'network.db'}")

    assert scenario.observing_agent_id == "agent_2"
    assert scenario.requesting_agent_ids == ("agent_1", "agent_3")
    assert scenario.negotiation_ids == ("negotiation_engineer_remote", "negotiation_sales_onsite")
    assert scenario.decision_context["active_load"] == 2
    assert [item["id"] for item in scenario.decision_context["inbound_requested_negotiations"]] == [
        "negotiation_engineer_remote",
        "negotiation_sales_onsite",
    ]
