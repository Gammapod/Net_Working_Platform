from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import create_engine

from net_working_platform.domain.model import AgentConnection, AgentConnectionState, NegotiationDecision, Node, NodeType
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


@dataclass(frozen=True)
class ReferralRelayScenario:
    db_url: str
    requesting_agent_id: str
    intermediary_agent_id: str
    referred_agent_id: str
    upstream_negotiation_id: str
    downstream_negotiation_id: str


@dataclass(frozen=True)
class ParallelInboundScenario:
    db_url: str
    observing_agent_id: str
    requesting_agent_ids: tuple[str, str]
    negotiation_ids: tuple[str, str]
    decision_context: dict[str, object]


def seed_inbound_request_scenario(
    db_url: str,
    *,
    subject: dict[str, object] | None = None,
) -> InboundRequestScenario:
    """Create a dev/test scenario for one-step LLM decision observation."""
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


def seed_referral_relay_scenario(db_url: str) -> ReferralRelayScenario:
    """Create a three-agent scenario where agent_2 can relay between two negotiations."""
    engine = create_engine(db_url)
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)

        nodes.add(Node(id="agent_1", type=NodeType.AGENT), display_name="Requesting Agent")
        nodes.add(Node(id="agent_2", type=NodeType.AGENT), display_name="Intermediary Agent")
        nodes.add(Node(id="agent_3", type=NodeType.AGENT), display_name="Referred Agent")
        agent_connections.add(AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE))
        agent_connections.add(AgentConnection("agent_2", "agent_3", AgentConnectionState.ACTIVE))

        ids = iter(["negotiation_agent1_agent2", "negotiation_agent2_agent3"])
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: next(ids),
            now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
        )
        upstream = service.request_negotiation(
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            subject={"need": "referral", "role": "engineer", "location": "remote"},
            max_open_negotiations=5,
        )
        service.respond_to_negotiation(
            negotiation_id=upstream.id,
            actor_agent_id="agent_2",
            decision=NegotiationDecision.ACCEPT,
        )
        service.send_message(
            negotiation_id=upstream.id,
            actor_agent_id="agent_1",
            body="Can you ask your trusted engineering contact whether remote backend roles are relevant?",
        )
        downstream = service.request_negotiation(
            from_agent_id="agent_2",
            to_agent_id="agent_3",
            subject={"need": "referral_check", "role": "engineer", "location": "remote"},
            max_open_negotiations=5,
        )
        service.respond_to_negotiation(
            negotiation_id=downstream.id,
            actor_agent_id="agent_3",
            decision=NegotiationDecision.ACCEPT,
        )

    return ReferralRelayScenario(
        db_url=db_url,
        requesting_agent_id="agent_1",
        intermediary_agent_id="agent_2",
        referred_agent_id="agent_3",
        upstream_negotiation_id="negotiation_agent1_agent2",
        downstream_negotiation_id="negotiation_agent2_agent3",
    )


def seed_parallel_inbound_scenario(db_url: str) -> ParallelInboundScenario:
    """Create two simultaneous inbound requests to one observing agent."""
    engine = create_engine(db_url)
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)

        for agent_id, name in [
            ("agent_1", "Engineer Requesting Agent"),
            ("agent_2", "Observing Agent"),
            ("agent_3", "Sales Requesting Agent"),
        ]:
            nodes.add(Node(id=agent_id, type=NodeType.AGENT), display_name=name)
        agent_connections.add(AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE))
        agent_connections.add(AgentConnection("agent_3", "agent_2", AgentConnectionState.ACTIVE))

        ids = iter(["negotiation_engineer_remote", "negotiation_sales_onsite"])
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: next(ids),
            now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
        )
        first = service.request_negotiation(
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            subject={"role": "engineer", "location": "remote"},
            max_open_negotiations=5,
        )
        second = service.request_negotiation(
            from_agent_id="agent_3",
            to_agent_id="agent_2",
            subject={"role": "sales", "location": "onsite"},
            max_open_negotiations=5,
        )
        decision_context = service.get_agent_decision_context(agent_id="agent_2", recent_event_limit=10)

    return ParallelInboundScenario(
        db_url=db_url,
        observing_agent_id="agent_2",
        requesting_agent_ids=("agent_1", "agent_3"),
        negotiation_ids=(first.id, second.id),
        decision_context=decision_context,
    )
