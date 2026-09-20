from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import create_engine

from net_working_platform.application.graph_snapshots import build_graph_snapshot
from net_working_platform.application.graph_mermaid import render_graph_snapshot_mermaid
from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    Negotiation,
    NegotiationState,
    Node,
    NodeType,
    ProtocolEvent,
    ProtocolEventType,
    RepresentationEdge,
    RepresentationState,
)
from net_working_platform.storage.graph_snapshots import SqlGraphSnapshotReader
from net_working_platform.storage.repositories import (
    SqlAgentConnectionRepository,
    SqlNegotiationRepository,
    SqlNodeRepository,
    SqlProtocolEventRepository,
    SqlRepresentationEdgeRepository,
)
from net_working_platform.storage.schema import metadata


@dataclass
class RecordingSnapshotReader:
    read_calls: list[str] = field(default_factory=list)

    def list_nodes(self) -> list[dict[str, object]]:
        self.read_calls.append("list_nodes")
        return [
            {
                "id": "agent_1",
                "type": "agent",
                "display_name": "Agent One",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
            {
                "id": "client_1",
                "type": "client",
                "display_name": None,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
        ]

    def list_agent_connections(self) -> list[dict[str, object]]:
        self.read_calls.append("list_agent_connections")
        return [
            {
                "from_agent_id": "agent_1",
                "to_agent_id": "agent_2",
                "state": "active",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            }
        ]

    def list_representation_edges(self) -> list[dict[str, object]]:
        self.read_calls.append("list_representation_edges")
        return [
            {
                "agent_id": "agent_1",
                "represented_node_id": "client_1",
                "represented_node_type": "client",
                "state": "active",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            }
        ]

    def list_negotiations(self) -> list[dict[str, object]]:
        self.read_calls.append("list_negotiations")
        return [
            {
                "id": "negotiation_1",
                "from_agent_id": "agent_1",
                "to_agent_id": "agent_2",
                "state": "open",
                "subject": {"role": "engineer"},
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            }
        ]

    def count_events_by_negotiation(self) -> dict[str, int]:
        self.read_calls.append("count_events_by_negotiation")
        return {"negotiation_1": 2}


def test_build_graph_snapshot_returns_viewer_ready_nodes_and_edges() -> None:
    """Protects INV-H-005."""
    reader = RecordingSnapshotReader()

    snapshot = build_graph_snapshot(
        reader,
        now=lambda: datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    assert snapshot["generated_at"] == "2026-01-03T00:00:00+00:00"
    assert snapshot["source"] == "current_database_state"
    assert snapshot["nodes"] == [
        {
            "id": "agent_1",
            "type": "agent",
            "label": "Agent One",
            "details": {
                "display_name": "Agent One",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
        },
        {
            "id": "client_1",
            "type": "client",
            "label": "client_1",
            "details": {
                "display_name": None,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
        },
    ]
    assert [edge["kind"] for edge in snapshot["edges"]] == [
        "agent_connection",
        "representation",
        "negotiation",
    ]
    assert [edge["label"] for edge in snapshot["edges"]] == ["active", "active", "open"]
    assert snapshot["edges"][2]["details"]["recent_event_count"] == 2
    assert reader.read_calls == [
        "list_nodes",
        "count_events_by_negotiation",
        "list_agent_connections",
        "list_representation_edges",
        "list_negotiations",
    ]


def test_sql_graph_snapshot_reader_reads_current_graph_state() -> None:
    """Protects INV-H-005."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)
        negotiations = SqlNegotiationRepository(connection)
        events = SqlProtocolEventRepository(connection)

        nodes.add(Node("agent_1", NodeType.AGENT), display_name="Agent One")
        nodes.add(Node("agent_2", NodeType.AGENT), display_name="Agent Two")
        nodes.add(Node("client_1", NodeType.CLIENT), display_name="Client One")
        agent_connections.add(AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE))
        representation_edges.add(RepresentationEdge("agent_1", "client_1", NodeType.CLIENT, RepresentationState.ACTIVE))
        negotiations.add(Negotiation("negotiation_1", "agent_1", "agent_2", NegotiationState.OPEN, {"role": "engineer"}))
        events.append(
            ProtocolEvent(
                type=ProtocolEventType.MESSAGE,
                actor_agent_id="agent_1",
                negotiation_id="negotiation_1",
                occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                payload={"body": "Hello"},
            )
        )

        reader = SqlGraphSnapshotReader(connection)
        snapshot = build_graph_snapshot(reader, now=lambda: datetime(2026, 1, 3, tzinfo=timezone.utc))

    assert [node["id"] for node in snapshot["nodes"]] == ["agent_1", "agent_2", "client_1"]
    assert {(edge["kind"], edge["source"], edge["target"], edge["state"]) for edge in snapshot["edges"]} == {
        ("agent_connection", "agent_1", "agent_2", "active"),
        ("representation", "agent_1", "client_1", "active"),
        ("negotiation", "agent_1", "agent_2", "open"),
    }
    negotiation_edge = next(edge for edge in snapshot["edges"] if edge["kind"] == "negotiation")
    assert negotiation_edge["details"]["subject"] == {"role": "engineer"}
    assert negotiation_edge["details"]["recent_event_count"] == 1


def test_render_graph_snapshot_mermaid_uses_short_labels_and_edge_styles() -> None:
    """Protects INV-H-005."""
    snapshot = {
        "nodes": [
            {"id": "agent_1", "label": "Agent One"},
            {"id": "agent_2", "label": "Agent Two"},
            {"id": "client_1", "label": "Client One"},
        ],
        "edges": [
            {
                "kind": "agent_connection",
                "source": "agent_1",
                "target": "agent_2",
                "label": "active",
            },
            {
                "kind": "representation",
                "source": "agent_1",
                "target": "client_1",
                "label": "active",
            },
            {
                "kind": "negotiation",
                "source": "agent_1",
                "target": "agent_2",
                "label": "open",
            },
        ],
    }

    assert render_graph_snapshot_mermaid(snapshot) == (
        "flowchart LR\n"
        "  agent_1[\"Agent One\"]\n"
        "  agent_2[\"Agent Two\"]\n"
        "  client_1[\"Client One\"]\n"
        "\n"
        "  agent_1 -->|\"active\"| agent_2\n"
        "  agent_1 -.->|\"active\"| client_1\n"
        "  agent_1 ==>|\"open\"| agent_2\n"
    )
