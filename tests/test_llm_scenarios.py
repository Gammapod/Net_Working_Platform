from __future__ import annotations

from pathlib import Path

from net_working_platform.experiments.scenarios import (
    seed_inbound_request_scenario,
    seed_parallel_inbound_scenario,
    seed_referral_relay_scenario,
    seed_two_client_two_principal_scenario,
)
from net_working_platform.application.graph_snapshots import build_graph_snapshot
from net_working_platform.storage.graph_snapshots import SqlGraphSnapshotReader
from sqlalchemy import create_engine
from datetime import datetime, timezone


def test_inbound_request_scenario_produces_observable_decision_context(tmp_path: Path) -> None:
    """Exploratory fixture smoke test; invariants are protected by narrower protocol tests."""
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
    """Exploratory fixture smoke test; invariants are protected by narrower protocol tests."""
    scenario = seed_referral_relay_scenario(f"sqlite+pysqlite:///{tmp_path / 'network.db'}")

    assert scenario.requesting_agent_id == "agent_1"
    assert scenario.intermediary_agent_id == "agent_2"
    assert scenario.referred_agent_id == "agent_3"
    assert scenario.upstream_negotiation_id == "negotiation_agent1_agent2"
    assert scenario.downstream_negotiation_id == "negotiation_agent2_agent3"


def test_parallel_inbound_scenario_exposes_two_requested_negotiations(tmp_path: Path) -> None:
    """Exploratory fixture smoke test; invariants are protected by narrower protocol tests."""
    scenario = seed_parallel_inbound_scenario(f"sqlite+pysqlite:///{tmp_path / 'network.db'}")

    assert scenario.observing_agent_id == "agent_2"
    assert scenario.requesting_agent_ids == ("agent_1", "agent_3")
    assert scenario.negotiation_ids == ("negotiation_engineer_remote", "negotiation_sales_onsite")
    assert scenario.decision_context["active_load"] == 2
    assert [item["id"] for item in scenario.decision_context["inbound_requested_negotiations"]] == [
        "negotiation_engineer_remote",
        "negotiation_sales_onsite",
    ]


def test_two_client_two_principal_scenario_creates_requested_starting_graph(tmp_path: Path) -> None:
    """Exploratory fixture smoke test; invariants are protected by narrower protocol tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"
    scenario = seed_two_client_two_principal_scenario(db_url)
    engine = create_engine(db_url)

    with engine.begin() as connection:
        snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 12, 30, tzinfo=timezone.utc),
        )

    assert scenario.client_agent_ids == ("client_agent_1", "client_agent_2")
    assert scenario.principal_agent_ids == ("principal_agent_1", "principal_agent_2")
    assert scenario.negotiation_ids == (
        "negotiation_client1_principal1",
        "negotiation_client1_principal2",
        "negotiation_client2_principal1",
    )
    assert {node["id"] for node in snapshot["nodes"]} == {
        "client_agent_1",
        "client_agent_2",
        "principal_agent_1",
        "principal_agent_2",
        "client_1",
        "client_2",
        "principal_1",
        "principal_2",
    }
    assert {
        (edge["kind"], edge["source"], edge["target"], edge["state"])
        for edge in snapshot["edges"]
    } == {
        ("representation", "client_agent_1", "client_1", "active"),
        ("representation", "client_agent_2", "client_2", "active"),
        ("representation", "principal_agent_1", "principal_1", "active"),
        ("representation", "principal_agent_2", "principal_2", "active"),
        ("agent_connection", "client_agent_1", "principal_agent_1", "active"),
        ("agent_connection", "client_agent_1", "principal_agent_2", "active"),
        ("agent_connection", "client_agent_2", "principal_agent_1", "active"),
        ("negotiation", "client_agent_1", "principal_agent_1", "open"),
        ("negotiation", "client_agent_1", "principal_agent_2", "open"),
        ("negotiation", "client_agent_2", "principal_agent_1", "open"),
    }
