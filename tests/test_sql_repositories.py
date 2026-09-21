from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine

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
from net_working_platform.storage.repositories import (
    SqlAgentConnectionRepository,
    SqlNegotiationRepository,
    SqlNodeRepository,
    SqlProtocolEventRepository,
    SqlRepresentationEdgeRepository,
)
from net_working_platform.storage.schema import metadata


def test_sql_repositories_round_trip_core_graph_records() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)

        nodes.add(Node(id="agent_1", type=NodeType.AGENT), display_name="Agent One")
        nodes.add(Node(id="agent_2", type=NodeType.AGENT), display_name="Agent Two")
        nodes.add(Node(id="client_1", type=NodeType.CLIENT), display_name="Client One")
        agent_connections.add(AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE))
        representation_edges.add(
            RepresentationEdge("agent_1", "client_1", NodeType.CLIENT, RepresentationState.ACTIVE)
        )

        assert agent_connections.get_between("agent_1", "agent_2") == AgentConnection(
            "agent_1", "agent_2", AgentConnectionState.ACTIVE
        )
        assert agent_connections.get_between("agent_2", "agent_1") is None
        assert representation_edges.get("agent_1", "client_1") == RepresentationEdge(
            "agent_1", "client_1", NodeType.CLIENT, RepresentationState.ACTIVE
        )


def test_sql_negotiation_repository_counts_requested_open_and_proposal_pending_as_active_load() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        negotiations = SqlNegotiationRepository(connection)
        for agent_id in ["agent_1", "agent_2"]:
            nodes.add(Node(id=agent_id, type=NodeType.AGENT))

        negotiations.add(Negotiation("requested_1", "agent_1", "agent_2", NegotiationState.REQUESTED, {}))
        negotiations.add(Negotiation("open_1", "agent_1", "agent_2", NegotiationState.OPEN, {}))
        negotiations.add(Negotiation("proposal_1", "agent_1", "agent_2", NegotiationState.PROPOSAL_PENDING, {}))
        negotiations.add(Negotiation("matched_1", "agent_1", "agent_2", NegotiationState.MATCHED, {}))
        negotiations.add(Negotiation("closed_1", "agent_1", "agent_2", NegotiationState.CLOSED, {}))

        assert negotiations.count_open_for_agent("agent_1") == 3


def test_sql_negotiation_repository_counts_inbound_requested_open_and_proposal_pending_as_active_load() -> None:
    """Protects INV-C-001."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        negotiations = SqlNegotiationRepository(connection)
        for agent_id in ["agent_1", "agent_2"]:
            nodes.add(Node(id=agent_id, type=NodeType.AGENT))

        negotiations.add(Negotiation("outbound_open", "agent_1", "agent_2", NegotiationState.OPEN, {}))
        negotiations.add(Negotiation("inbound_requested", "agent_2", "agent_1", NegotiationState.REQUESTED, {}))
        negotiations.add(Negotiation("inbound_open", "agent_2", "agent_1", NegotiationState.OPEN, {}))
        negotiations.add(Negotiation("inbound_proposal", "agent_2", "agent_1", NegotiationState.PROPOSAL_PENDING, {}))
        negotiations.add(Negotiation("inbound_matched", "agent_2", "agent_1", NegotiationState.MATCHED, {}))
        negotiations.add(Negotiation("inbound_closed", "agent_2", "agent_1", NegotiationState.CLOSED, {}))

        assert negotiations.count_open_for_agent("agent_1") == 4


def test_sql_repositories_round_trip_negotiation_and_events_in_order() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        negotiations = SqlNegotiationRepository(connection)
        events = SqlProtocolEventRepository(connection)
        for agent_id in ["agent_1", "agent_2"]:
            nodes.add(Node(id=agent_id, type=NodeType.AGENT))

        negotiation = Negotiation(
            id="negotiation_1",
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            state=NegotiationState.REQUESTED,
            subject={"role": "engineer"},
        )
        negotiations.add(negotiation)
        assert negotiations.get("negotiation_1") == negotiation

        updated = Negotiation(
            id="negotiation_1",
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            state=NegotiationState.OPEN,
            subject={"role": "engineer"},
        )
        negotiations.save(updated)
        assert negotiations.get("negotiation_1") == updated

        first = ProtocolEvent(
            type=ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            payload={"subject": {"role": "engineer"}},
        )
        second = ProtocolEvent(
            type=ProtocolEventType.MESSAGE,
            actor_agent_id="agent_2",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            payload={"body": "Interested."},
        )
        events.append(second)
        events.append(first)

        assert events.list_for_negotiation("negotiation_1") == [first, second]
