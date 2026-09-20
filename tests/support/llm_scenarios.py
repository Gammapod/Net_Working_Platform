from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import create_engine

from net_working_platform.domain.model import AgentConnection, AgentConnectionState, Node, NodeType
from net_working_platform.storage.repositories import SqlAgentConnectionRepository, SqlNodeRepository
from net_working_platform.storage.schema import metadata
from net_working_platform.storage.services import create_sql_negotiation_service


@dataclass(frozen=True)
class InboundRequestScenario:
    db_url: str
    observing_agent_id: str
    requesting_agent_id: str
    negotiation_id: str
    decision_context: dict[str, object]


def seed_inbound_request_scenario(
    db_url: str,
    *,
    subject: dict[str, object] | None = None,
) -> InboundRequestScenario:
    """Create a dev/test-only scenario for one-step LLM decision observation.

    The scenario creates two agents, connects agent_1 to agent_2, opens a
    requested negotiation from agent_1 to agent_2, and returns agent_2's
    structured decision context.
    """
    engine = create_engine(db_url)
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)

        nodes.add(Node(id="agent_1", type=NodeType.AGENT), display_name="Requesting Agent")
        nodes.add(Node(id="agent_2", type=NodeType.AGENT), display_name="Observing Agent")
        agent_connections.add(AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE))

        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "negotiation_inbound_request",
            now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
        )
        negotiation = service.request_negotiation(
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            subject=subject or {"role": "engineer", "location": "remote"},
            max_open_negotiations=5,
        )
        decision_context = service.get_agent_decision_context(agent_id="agent_2", recent_event_limit=10)

    return InboundRequestScenario(
        db_url=db_url,
        observing_agent_id="agent_2",
        requesting_agent_id="agent_1",
        negotiation_id=negotiation.id,
        decision_context=decision_context,
    )
