from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine

from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    NegotiationDecision,
    NegotiationState,
    Node,
    NodeType,
    ProtocolEventType,
)
from net_working_platform.storage.repositories import SqlAgentConnectionRepository, SqlNodeRepository
from net_working_platform.storage.schema import metadata
from net_working_platform.storage.services import create_sql_negotiation_service


def test_sql_backed_negotiation_service_runs_full_lifecycle() -> None:
    """Protects INV-G-001, INV-N-001..005, INV-H-001, and INV-H-003."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    times = iter(
        [
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
            for index in range(5)
        ]
    )

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        nodes.add(Node(id="agent_1", type=NodeType.AGENT))
        nodes.add(Node(id="agent_2", type=NodeType.AGENT))
        agent_connections.add(AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE))
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "negotiation_1",
            now=lambda: next(times),
        )

        requested = service.request_negotiation(
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            subject={"role": "engineer"},
            max_open_negotiations=2,
        )
        opened = service.respond_to_negotiation(
            negotiation_id=requested.id,
            actor_agent_id="agent_2",
            decision=NegotiationDecision.ACCEPT,
        )
        service.send_message(
            negotiation_id=requested.id,
            actor_agent_id="agent_1",
            body="Candidate can interview Tuesday.",
        )
        service.propose_match(
            negotiation_id=requested.id,
            actor_agent_id="agent_1",
            proposal={"candidate_id": "client_1", "principal_id": "principal_1"},
        )
        matched = service.accept_match(negotiation_id=requested.id, actor_agent_id="agent_2")
        history = service.get_negotiation_history(requested.id)

    assert requested.state == NegotiationState.REQUESTED
    assert opened.state == NegotiationState.OPEN
    assert matched.state == NegotiationState.MATCHED
    assert [event.type for event in history] == [
        ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
        ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
        ProtocolEventType.MESSAGE,
        ProtocolEventType.MATCH_PROPOSED,
        ProtocolEventType.MATCH_ACCEPTED,
    ]
    assert history[2].payload == {"body": "Candidate can interview Tuesday."}
