from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from net_working_platform.experiments.scenarios import seed_weak_discovery_scenario
from net_working_platform.storage.repositories import SqlAgentConnectionRepository, SqlProtocolEventRepository
from net_working_platform.storage.services import create_sql_discovery_service


def test_weak_discovery_scenario_allows_same_field_probe_and_connection(tmp_path: Path) -> None:
    """Exploratory fixture smoke test; discovery invariants are protected by service tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'weak_discovery.db'}"
    scenario = seed_weak_discovery_scenario(db_url)
    engine = create_engine(db_url)

    with engine.begin() as connection:
        service = create_sql_discovery_service(
            connection,
            now=lambda: datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc),
        )

        assert service.list_discoverable_agents(
            actor_agent_id=scenario.marketing_client_agent_ids[0],
            field="marketing",
        ) == [
            {
                "agent_id": scenario.marketing_client_agent_ids[1],
                "field": "marketing",
                "rationale": {
                    "reason": "same_field",
                    "field": "marketing",
                    "target_represented_type": "client",
                    "target_represented_id": "marketing_client_2",
                },
            },
            {
                "agent_id": scenario.marketing_principal_agent_id,
                "field": "marketing",
                "rationale": {
                    "reason": "same_field",
                    "field": "marketing",
                    "target_represented_type": "principal",
                    "target_represented_id": "marketing_principal",
                },
            },
        ]

        service.probe_weak_connection(
            actor_agent_id=scenario.marketing_client_agent_ids[0],
            target_agent_id=scenario.marketing_principal_agent_id,
            field="marketing",
            criteria={"role_field": "marketing"},
        )
        created = service.request_contact(
            actor_agent_id=scenario.marketing_client_agent_ids[0],
            target_agent_id=scenario.marketing_principal_agent_id,
            field="marketing",
            reason="Client is seeking marketing opportunities.",
        )

        assert SqlAgentConnectionRepository(connection).get_between(
            scenario.marketing_client_agent_ids[0],
            scenario.marketing_principal_agent_id,
        ) == created
        assert [event.type.value for event in SqlProtocolEventRepository(connection).list_recent_for_agent(
            scenario.marketing_client_agent_ids[0],
            [],
            10,
        )] == []


def test_weak_discovery_scenario_blocks_cross_field_probe_and_connection(tmp_path: Path) -> None:
    """Exploratory fixture smoke test; discovery invariants are protected by service tests."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'weak_discovery.db'}"
    scenario = seed_weak_discovery_scenario(db_url)
    engine = create_engine(db_url)

    with engine.begin() as connection:
        service = create_sql_discovery_service(
            connection,
            now=lambda: datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc),
        )

        with pytest.raises(PermissionError, match="weak discovery edge"):
            service.probe_weak_connection(
                actor_agent_id=scenario.marketing_client_agent_ids[0],
                target_agent_id=scenario.programming_principal_agent_id,
                field="marketing",
                criteria={"role_field": "marketing"},
            )

        with pytest.raises(PermissionError, match="weak discovery edge"):
            service.request_contact(
                actor_agent_id=scenario.marketing_client_agent_ids[0],
                target_agent_id=scenario.programming_principal_agent_id,
                field="marketing",
                reason="This should be blocked because the fields do not match.",
            )
