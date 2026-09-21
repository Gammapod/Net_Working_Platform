from sqlalchemy import CheckConstraint

from net_working_platform.storage.schema import (
    agent_connections,
    metadata,
    negotiations,
    nodes,
    protocol_events,
    representation_edges,
)


def test_storage_schema_declares_mvp_tables() -> None:
    assert set(metadata.tables) == {
        "nodes",
        "agent_connections",
        "representation_edges",
        "negotiations",
        "protocol_events",
    }


def test_agent_connections_are_directional() -> None:
    assert [column.name for column in agent_connections.primary_key.columns] == [
        "from_agent_id",
        "to_agent_id",
    ]


def test_core_table_columns_match_repository_contracts() -> None:
    assert {column.name for column in nodes.columns} >= {"id", "type", "display_name", "created_at"}
    assert {column.name for column in representation_edges.columns} >= {
        "agent_id",
        "represented_node_id",
        "represented_node_type",
        "state",
    }
    assert {column.name for column in negotiations.columns} >= {
        "id",
        "from_agent_id",
        "to_agent_id",
        "state",
        "subject",
    }
    assert {column.name for column in protocol_events.columns} >= {
        "id",
        "negotiation_id",
        "actor_agent_id",
        "type",
        "occurred_at",
        "payload",
    }


def test_storage_schema_uses_check_constraints_for_domain_enums() -> None:
    check_sql = "\n".join(
        str(constraint.sqltext)
        for table in metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )

    assert "agent" in check_sql
    assert "client" in check_sql
    assert "principal" in check_sql
    assert "requested" in check_sql
    assert "open" in check_sql
    assert "proposal_pending" in check_sql
    assert "matched" in check_sql
    assert "closed" in check_sql
