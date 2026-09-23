from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import create_engine

from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    NegotiationDecision,
    Node,
    NodeType,
    FactKind,
    RepresentationEdge,
    RepresentationState,
    RepresentedPartyFact,
    RepresentedPartyProfile,
    WeakDiscoveryEdge,
    WeakDiscoveryState,
)
from net_working_platform.storage.repositories import (
    SqlAgentConnectionRepository,
    SqlNodeRepository,
    SqlRepresentationEdgeRepository,
    SqlWeakDiscoveryEdgeRepository,
)
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


@dataclass(frozen=True)
class TwoClientTwoPrincipalScenario:
    db_url: str
    client_agent_ids: tuple[str, str]
    principal_agent_ids: tuple[str, str]
    client_ids: tuple[str, str]
    principal_ids: tuple[str, str]
    negotiation_ids: tuple[str, str, str]


@dataclass(frozen=True)
class MarketScenario:
    db_url: str
    client_agent_ids: tuple[str, ...]
    principal_agent_ids: tuple[str, ...]
    client_ids: tuple[str, ...]
    principal_ids: tuple[str, ...]
    negotiation_ids: tuple[str, ...]


@dataclass(frozen=True)
class PairwiseStrategyScenario:
    db_url: str
    client_agent_id: str
    principal_agent_id: str
    client_id: str
    principal_id: str
    negotiation_id: str
    client_strategy_id: str
    principal_strategy_id: str
    client_facts: dict[str, object]
    principal_facts: dict[str, object]
    represented_party_profiles_by_agent: dict[str, list[RepresentedPartyProfile]]


@dataclass(frozen=True)
class MultiPartyContactScenario:
    db_url: str
    scenario_id: str
    client_agent_id: str
    principal_agent_id: str
    client_ids: tuple[str, str]
    principal_ids: tuple[str, str]
    client_summaries: dict[str, dict[str, object]]
    principal_summaries: dict[str, dict[str, object]]


@dataclass(frozen=True)
class MultiContactPortfolioChoiceScenario:
    db_url: str
    scenario_id: str
    actor_agent_id: str
    field: str
    contact_limit: int
    represented_portfolio: tuple[dict[str, object], ...]
    candidate_agents: tuple[str, ...]
    candidate_metadata: dict[str, dict[str, object]]


@dataclass(frozen=True)
class OpenMarketNetworkingScenario:
    db_url: str
    scenario_id: str
    agent_fields: dict[str, str]
    represented_types: dict[str, str]
    represented_portfolios: dict[str, tuple[dict[str, object], ...]]


@dataclass(frozen=True)
class WeakDiscoveryScenario:
    db_url: str
    marketing_client_agent_ids: tuple[str, str]
    programming_client_agent_id: str
    marketing_principal_agent_id: str
    programming_principal_agent_id: str
    agent_fields: dict[str, str]


def seed_weak_discovery_scenario(db_url: str) -> WeakDiscoveryScenario:
    """Create a five-agent weak discovery scenario by field.

    Two client agents and one principal agent are in marketing; one client agent
    and one principal agent are in programming. Weak discovery edges are created
    only between agents with the same field, so marketing agents can probe and
    connect with marketing agents but not programming agents.
    """
    engine = create_engine(db_url)
    metadata.create_all(engine)

    agent_fields = {
        "marketing_client_agent_1": "marketing",
        "marketing_client_agent_2": "marketing",
        "programming_client_agent": "programming",
        "marketing_principal_agent": "marketing",
        "programming_principal_agent": "programming",
    }
    represented_nodes = {
        "marketing_client_agent_1": ("marketing_client_1", NodeType.CLIENT, "Marketing Client 1"),
        "marketing_client_agent_2": ("marketing_client_2", NodeType.CLIENT, "Marketing Client 2"),
        "programming_client_agent": ("programming_client", NodeType.CLIENT, "Programming Client"),
        "marketing_principal_agent": ("marketing_principal", NodeType.PRINCIPAL, "Marketing Principal"),
        "programming_principal_agent": ("programming_principal", NodeType.PRINCIPAL, "Programming Principal"),
    }

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)
        weak_edges = SqlWeakDiscoveryEdgeRepository(connection)

        for agent_id, field in agent_fields.items():
            nodes.add(Node(id=agent_id, type=NodeType.AGENT), display_name=agent_id.replace("_", " ").title())
            represented_id, represented_type, display_name = represented_nodes[agent_id]
            nodes.add(Node(id=represented_id, type=represented_type), display_name=display_name)
            representation_edges.add(
                RepresentationEdge(
                    agent_id=agent_id,
                    represented_node_id=represented_id,
                    represented_node_type=represented_type,
                    state=RepresentationState.ACTIVE,
                )
            )

        for from_agent_id, from_field in agent_fields.items():
            for to_agent_id, to_field in agent_fields.items():
                if from_agent_id == to_agent_id or from_field != to_field:
                    continue
                weak_edges.add(
                    WeakDiscoveryEdge(
                        from_agent_id=from_agent_id,
                        to_agent_id=to_agent_id,
                        field=from_field,
                        state=WeakDiscoveryState.AVAILABLE,
                        rationale={
                            "reason": "same_field",
                            "field": from_field,
                            "target_represented_type": represented_nodes[to_agent_id][1].value,
                            "target_represented_id": represented_nodes[to_agent_id][0],
                        },
                    )
                )

    return WeakDiscoveryScenario(
        db_url=db_url,
        marketing_client_agent_ids=("marketing_client_agent_1", "marketing_client_agent_2"),
        programming_client_agent_id="programming_client_agent",
        marketing_principal_agent_id="marketing_principal_agent",
        programming_principal_agent_id="programming_principal_agent",
        agent_fields=agent_fields,
    )


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


def seed_two_client_two_principal_scenario(db_url: str) -> TwoClientTwoPrincipalScenario:
    """Create a two-client-agent/two-principal-agent starting graph.

    The first client agent has open negotiations with both principal agents.
    The second client agent has an open negotiation with only the first principal
    agent and no connection to the second principal agent.
    """
    engine = create_engine(db_url)
    metadata.create_all(engine)

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)

        for node_id, node_type, display_name in [
            ("client_agent_1", NodeType.AGENT, "Client Agent 1"),
            ("client_agent_2", NodeType.AGENT, "Client Agent 2"),
            ("principal_agent_1", NodeType.AGENT, "Principal Agent 1"),
            ("principal_agent_2", NodeType.AGENT, "Principal Agent 2"),
            ("client_1", NodeType.CLIENT, "Client 1"),
            ("client_2", NodeType.CLIENT, "Client 2"),
            ("principal_1", NodeType.PRINCIPAL, "Principal 1"),
            ("principal_2", NodeType.PRINCIPAL, "Principal 2"),
        ]:
            nodes.add(Node(id=node_id, type=node_type), display_name=display_name)

        for edge in [
            RepresentationEdge("client_agent_1", "client_1", NodeType.CLIENT, RepresentationState.ACTIVE),
            RepresentationEdge("client_agent_2", "client_2", NodeType.CLIENT, RepresentationState.ACTIVE),
            RepresentationEdge("principal_agent_1", "principal_1", NodeType.PRINCIPAL, RepresentationState.ACTIVE),
            RepresentationEdge("principal_agent_2", "principal_2", NodeType.PRINCIPAL, RepresentationState.ACTIVE),
        ]:
            representation_edges.add(edge)

        for agent_connection in [
            AgentConnection("client_agent_1", "principal_agent_1", AgentConnectionState.ACTIVE),
            AgentConnection("client_agent_1", "principal_agent_2", AgentConnectionState.ACTIVE),
            AgentConnection("client_agent_2", "principal_agent_1", AgentConnectionState.ACTIVE),
        ]:
            agent_connections.add(agent_connection)

        ids = iter(
            [
                "negotiation_client1_principal1",
                "negotiation_client1_principal2",
                "negotiation_client2_principal1",
            ]
        )
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: next(ids),
            now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
        )
        negotiation_specs = [
            (
                "client_agent_1",
                "principal_agent_1",
                {"client_id": "client_1", "principal_id": "principal_1", "role": "backend engineer"},
            ),
            (
                "client_agent_1",
                "principal_agent_2",
                {"client_id": "client_1", "principal_id": "principal_2", "role": "platform engineer"},
            ),
            (
                "client_agent_2",
                "principal_agent_1",
                {"client_id": "client_2", "principal_id": "principal_1", "role": "data engineer"},
            ),
        ]
        negotiations = []
        for from_agent_id, to_agent_id, subject in negotiation_specs:
            negotiation = service.request_negotiation(
                from_agent_id=from_agent_id,
                to_agent_id=to_agent_id,
                subject=subject,
                max_open_negotiations=5,
            )
            service.respond_to_negotiation(
                negotiation_id=negotiation.id,
                actor_agent_id=to_agent_id,
                decision=NegotiationDecision.ACCEPT,
            )
            negotiations.append(negotiation)

    return TwoClientTwoPrincipalScenario(
        db_url=db_url,
        client_agent_ids=("client_agent_1", "client_agent_2"),
        principal_agent_ids=("principal_agent_1", "principal_agent_2"),
        client_ids=("client_1", "client_2"),
        principal_ids=("principal_1", "principal_2"),
        negotiation_ids=tuple(negotiation.id for negotiation in negotiations),
    )


def seed_market_scenario(
    db_url: str,
    *,
    client_count: int,
    principal_count: int,
    negotiations_per_client: int = 2,
) -> MarketScenario:
    """Create a deterministic many-client/many-principal experiment market."""
    if client_count < 1:
        raise ValueError("client_count must be at least 1")
    if principal_count < 1:
        raise ValueError("principal_count must be at least 1")
    if negotiations_per_client < 1:
        raise ValueError("negotiations_per_client must be at least 1")

    negotiations_per_client = min(negotiations_per_client, principal_count)
    engine = create_engine(db_url)
    metadata.create_all(engine)

    client_agent_ids = tuple(f"client_agent_{index}" for index in range(1, client_count + 1))
    principal_agent_ids = tuple(f"principal_agent_{index}" for index in range(1, principal_count + 1))
    client_ids = tuple(f"client_{index}" for index in range(1, client_count + 1))
    principal_ids = tuple(f"principal_{index}" for index in range(1, principal_count + 1))
    negotiation_ids = tuple(
        f"negotiation_client{client_index}_principal{((client_index + offset - 2) % principal_count) + 1}"
        for client_index in range(1, client_count + 1)
        for offset in range(1, negotiations_per_client + 1)
    )

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)

        for index, agent_id in enumerate(client_agent_ids, start=1):
            nodes.add(Node(id=agent_id, type=NodeType.AGENT), display_name=f"Client Agent {index}")
        for index, agent_id in enumerate(principal_agent_ids, start=1):
            nodes.add(Node(id=agent_id, type=NodeType.AGENT), display_name=f"Principal Agent {index}")
        for index, client_id in enumerate(client_ids, start=1):
            nodes.add(Node(id=client_id, type=NodeType.CLIENT), display_name=f"Client {index}")
        for index, principal_id in enumerate(principal_ids, start=1):
            nodes.add(Node(id=principal_id, type=NodeType.PRINCIPAL), display_name=f"Principal {index}")

        for agent_id, client_id in zip(client_agent_ids, client_ids, strict=True):
            representation_edges.add(RepresentationEdge(agent_id, client_id, NodeType.CLIENT, RepresentationState.ACTIVE))
        for agent_id, principal_id in zip(principal_agent_ids, principal_ids, strict=True):
            representation_edges.add(RepresentationEdge(agent_id, principal_id, NodeType.PRINCIPAL, RepresentationState.ACTIVE))

        for client_index, client_agent_id in enumerate(client_agent_ids, start=1):
            for offset in range(negotiations_per_client):
                principal_index = ((client_index + offset - 1) % principal_count) + 1
                principal_agent_id = f"principal_agent_{principal_index}"
                agent_connections.add(
                    AgentConnection(client_agent_id, principal_agent_id, AgentConnectionState.ACTIVE)
                )

        ids = iter(negotiation_ids)
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: next(ids),
            now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
        )
        for client_index, client_agent_id in enumerate(client_agent_ids, start=1):
            for offset in range(negotiations_per_client):
                principal_index = ((client_index + offset - 1) % principal_count) + 1
                principal_agent_id = f"principal_agent_{principal_index}"
                negotiation = service.request_negotiation(
                    from_agent_id=client_agent_id,
                    to_agent_id=principal_agent_id,
                    subject={
                        "client_id": f"client_{client_index}",
                        "principal_id": f"principal_{principal_index}",
                        "role": _market_role(client_index, principal_index),
                        "market_scenario": "parameterized",
                    },
                    max_open_negotiations=max(negotiations_per_client + 1, 5),
                )
                service.respond_to_negotiation(
                    negotiation_id=negotiation.id,
                    actor_agent_id=principal_agent_id,
                    decision=NegotiationDecision.ACCEPT,
                )

    return MarketScenario(
        db_url=db_url,
        client_agent_ids=client_agent_ids,
        principal_agent_ids=principal_agent_ids,
        client_ids=client_ids,
        principal_ids=principal_ids,
        negotiation_ids=negotiation_ids,
    )


def seed_pairwise_strategy_scenario(
    db_url: str,
    *,
    client_strategy_id: str,
    principal_strategy_id: str,
    client_facts: dict[str, object] | None = None,
    principal_facts: dict[str, object] | None = None,
) -> PairwiseStrategyScenario:
    """Create a one-client/one-principal open negotiation for pairwise strategy tests."""
    engine = create_engine(db_url)
    metadata.create_all(engine)

    client_facts = client_facts or {
        "client_id": "client",
        "target_field": "software engineering",
        "experience": "backend Python services and data pipelines",
        "availability": "can start within two weeks",
        "compensation_target": "market competitive",
    }
    principal_facts = principal_facts or {
        "principal_id": "principal",
        "role": "backend engineer",
        "hard_minimums": ["Python", "API development", "can start within one month"],
        "compensation_band": "market competitive",
        "evidence_preferences": ["recent project examples", "references"],
    }
    represented_party_profiles_by_agent = _pairwise_fact_profiles_by_agent()

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)

        for node_id, node_type, display_name in [
            ("client_agent", NodeType.AGENT, "Client Strategy Agent"),
            ("principal_agent", NodeType.AGENT, "Principal Strategy Agent"),
            ("client", NodeType.CLIENT, "Pairwise Client"),
            ("principal", NodeType.PRINCIPAL, "Pairwise Principal"),
        ]:
            nodes.add(Node(id=node_id, type=node_type), display_name=display_name)

        representation_edges.add(
            RepresentationEdge("client_agent", "client", NodeType.CLIENT, RepresentationState.ACTIVE)
        )
        representation_edges.add(
            RepresentationEdge("principal_agent", "principal", NodeType.PRINCIPAL, RepresentationState.ACTIVE)
        )
        agent_connections.add(AgentConnection("client_agent", "principal_agent", AgentConnectionState.ACTIVE))

        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "negotiation_pairwise",
            now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
        )
        negotiation = service.request_negotiation(
            from_agent_id="client_agent",
            to_agent_id="principal_agent",
            subject={
                "client_id": "client",
                "principal_id": "principal",
                "role": principal_facts.get("role", "backend engineer"),
                "client_strategy_id": client_strategy_id,
                "principal_strategy_id": principal_strategy_id,
            },
            max_open_negotiations=5,
        )
        service.respond_to_negotiation(
            negotiation_id=negotiation.id,
            actor_agent_id="principal_agent",
            decision=NegotiationDecision.ACCEPT,
        )

    return PairwiseStrategyScenario(
        db_url=db_url,
        client_agent_id="client_agent",
        principal_agent_id="principal_agent",
        client_id="client",
        principal_id="principal",
        negotiation_id="negotiation_pairwise",
        client_strategy_id=client_strategy_id,
        principal_strategy_id=principal_strategy_id,
        client_facts=client_facts,
        principal_facts=principal_facts,
        represented_party_profiles_by_agent=represented_party_profiles_by_agent,
    )


def seed_multi_party_contact_scenario(db_url: str) -> MultiPartyContactScenario:
    """Create two contacted agents, each representing two parties.

    The scenario is intentionally small for networking-topic experiments: the
    client-side agent has one existing directional contact to the principal-side
    agent and must choose exactly one client topic plus one principal topic when
    opening a negotiation request.
    """
    engine = create_engine(db_url)
    metadata.create_all(engine)
    client_summaries: dict[str, dict[str, object]] = {
        "client_marketing_generalist": {
            "represented_party_id": "client_marketing_generalist",
            "represented_party_type": "client",
            "field": "marketing",
            "summary": "Marketing generalist with campaign operations and lifecycle email experience.",
            "target_role": "marketing coordinator",
            "priority": "quick placement in marketing",
        },
        "client_backend_engineer": {
            "represented_party_id": "client_backend_engineer",
            "represented_party_type": "client",
            "field": "software engineering",
            "summary": "Backend engineer with Python API and data pipeline experience.",
            "target_role": "backend engineer",
            "priority": "backend role with growth path",
        },
    }
    principal_summaries: dict[str, dict[str, object]] = {
        "principal_marketing_role": {
            "represented_party_id": "principal_marketing_role",
            "represented_party_type": "principal",
            "field": "marketing",
            "summary": "Hiring for marketing coordinator supporting campaigns and lifecycle email.",
            "role": "marketing coordinator",
            "priority": "fill quickly with relevant campaign experience",
        },
        "principal_data_role": {
            "represented_party_id": "principal_data_role",
            "represented_party_type": "principal",
            "field": "data engineering",
            "summary": "Hiring for data engineer focused on warehouse modeling and analytics pipelines.",
            "role": "data engineer",
            "priority": "strong data modeling background",
        },
    }

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        nodes.add(Node(id="client_portfolio_agent", type=NodeType.AGENT), display_name="Client Portfolio Agent")
        nodes.add(Node(id="principal_portfolio_agent", type=NodeType.AGENT), display_name="Principal Portfolio Agent")
        for client_id in client_summaries:
            nodes.add(Node(id=client_id, type=NodeType.CLIENT), display_name=client_id.replace("_", " ").title())
            representation_edges.add(RepresentationEdge("client_portfolio_agent", client_id, NodeType.CLIENT, RepresentationState.ACTIVE))
        for principal_id in principal_summaries:
            nodes.add(Node(id=principal_id, type=NodeType.PRINCIPAL), display_name=principal_id.replace("_", " ").title())
            representation_edges.add(RepresentationEdge("principal_portfolio_agent", principal_id, NodeType.PRINCIPAL, RepresentationState.ACTIVE))
        agent_connections.add(AgentConnection("client_portfolio_agent", "principal_portfolio_agent", AgentConnectionState.ACTIVE))

    return MultiPartyContactScenario(
        db_url=db_url,
        scenario_id="clear_marketing_fit",
        client_agent_id="client_portfolio_agent",
        principal_agent_id="principal_portfolio_agent",
        client_ids=tuple(client_summaries),
        principal_ids=tuple(principal_summaries),
        client_summaries=client_summaries,
        principal_summaries=principal_summaries,
    )


def seed_ambiguous_multi_party_contact_scenario(db_url: str) -> MultiPartyContactScenario:
    """Create a portfolio contact scenario with two plausible topic pairs."""
    engine = create_engine(db_url)
    metadata.create_all(engine)
    client_summaries: dict[str, dict[str, object]] = {
        "client_backend_api_engineer": {
            "represented_party_id": "client_backend_api_engineer",
            "represented_party_type": "client",
            "field": "software engineering",
            "summary": "Backend engineer strongest in Python APIs, reliability, and some data pipeline work.",
            "target_role": "backend/platform engineer",
            "priority": "prefer growth path and strong role fit over fastest placement",
        },
        "client_data_pipeline_engineer": {
            "represented_party_id": "client_data_pipeline_engineer",
            "represented_party_type": "client",
            "field": "data engineering",
            "summary": "Data pipeline engineer with Python ETL, warehouse modeling, and analytics support experience.",
            "target_role": "data engineer or backend data role",
            "priority": "quick placement is important, but avoid roles with no data work",
        },
    }
    principal_summaries: dict[str, dict[str, object]] = {
        "principal_platform_api_role": {
            "represented_party_id": "principal_platform_api_role",
            "represented_party_type": "principal",
            "field": "software engineering",
            "summary": "Hiring a platform API engineer for Python services with reliability and light data integration work.",
            "role": "platform API engineer",
            "priority": "strong backend API fit and long-term growth potential",
        },
        "principal_data_platform_role": {
            "represented_party_id": "principal_data_platform_role",
            "represented_party_type": "principal",
            "field": "data engineering",
            "summary": "Hiring a data platform engineer for Python pipelines, warehouse modeling, and analytics enablement.",
            "role": "data platform engineer",
            "priority": "fill soon with evidence of data pipeline ownership",
        },
    }

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        nodes.add(Node(id="client_portfolio_agent", type=NodeType.AGENT), display_name="Client Portfolio Agent")
        nodes.add(Node(id="principal_portfolio_agent", type=NodeType.AGENT), display_name="Principal Portfolio Agent")
        for client_id in client_summaries:
            nodes.add(Node(id=client_id, type=NodeType.CLIENT), display_name=client_id.replace("_", " ").title())
            representation_edges.add(RepresentationEdge("client_portfolio_agent", client_id, NodeType.CLIENT, RepresentationState.ACTIVE))
        for principal_id in principal_summaries:
            nodes.add(Node(id=principal_id, type=NodeType.PRINCIPAL), display_name=principal_id.replace("_", " ").title())
            representation_edges.add(RepresentationEdge("principal_portfolio_agent", principal_id, NodeType.PRINCIPAL, RepresentationState.ACTIVE))
        agent_connections.add(AgentConnection("client_portfolio_agent", "principal_portfolio_agent", AgentConnectionState.ACTIVE))

    return MultiPartyContactScenario(
        db_url=db_url,
        scenario_id="ambiguous_two_plausible_pairs",
        client_agent_id="client_portfolio_agent",
        principal_agent_id="principal_portfolio_agent",
        client_ids=tuple(client_summaries),
        principal_ids=tuple(principal_summaries),
        client_summaries=client_summaries,
        principal_summaries=principal_summaries,
    )


def seed_bad_fit_multi_party_contact_scenario(db_url: str) -> MultiPartyContactScenario:
    """Create a portfolio contact scenario where client topics should not fit principal topics."""
    engine = create_engine(db_url)
    metadata.create_all(engine)
    client_summaries: dict[str, dict[str, object]] = {
        "client_barista": {
            "represented_party_id": "client_barista",
            "represented_party_type": "client",
            "field": "hospitality",
            "summary": "Barista with cafe operations and customer service experience, seeking local hospitality work.",
            "target_role": "barista or cafe shift lead",
            "priority": "local hospitality placement only",
        },
        "client_graphic_designer": {
            "represented_party_id": "client_graphic_designer",
            "represented_party_type": "client",
            "field": "graphic design",
            "summary": "Graphic designer focused on brand identity, print layouts, and social media assets.",
            "target_role": "graphic designer",
            "priority": "creative design role with portfolio review",
        },
    }
    principal_summaries: dict[str, dict[str, object]] = {
        "principal_senior_ml_role": {
            "represented_party_id": "principal_senior_ml_role",
            "represented_party_type": "principal",
            "field": "machine learning",
            "summary": "Hiring a senior ML engineer requiring production model deployment and Python ML systems experience.",
            "role": "senior machine learning engineer",
            "priority": "must have production ML engineering experience",
        },
        "principal_security_architect_role": {
            "represented_party_id": "principal_security_architect_role",
            "represented_party_type": "principal",
            "field": "cybersecurity",
            "summary": "Hiring a security architect requiring threat modeling, cloud security, and incident response leadership.",
            "role": "security architect",
            "priority": "must have senior cybersecurity architecture background",
        },
    }

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)
        agent_connections = SqlAgentConnectionRepository(connection)
        nodes.add(Node(id="client_portfolio_agent", type=NodeType.AGENT), display_name="Client Portfolio Agent")
        nodes.add(Node(id="principal_portfolio_agent", type=NodeType.AGENT), display_name="Principal Portfolio Agent")
        for client_id in client_summaries:
            nodes.add(Node(id=client_id, type=NodeType.CLIENT), display_name=client_id.replace("_", " ").title())
            representation_edges.add(RepresentationEdge("client_portfolio_agent", client_id, NodeType.CLIENT, RepresentationState.ACTIVE))
        for principal_id in principal_summaries:
            nodes.add(Node(id=principal_id, type=NodeType.PRINCIPAL), display_name=principal_id.replace("_", " ").title())
            representation_edges.add(RepresentationEdge("principal_portfolio_agent", principal_id, NodeType.PRINCIPAL, RepresentationState.ACTIVE))
        agent_connections.add(AgentConnection("client_portfolio_agent", "principal_portfolio_agent", AgentConnectionState.ACTIVE))

    return MultiPartyContactScenario(
        db_url=db_url,
        scenario_id="bad_fit_rejection",
        client_agent_id="client_portfolio_agent",
        principal_agent_id="principal_portfolio_agent",
        client_ids=tuple(client_summaries),
        principal_ids=tuple(principal_summaries),
        client_summaries=client_summaries,
        principal_summaries=principal_summaries,
    )


def seed_multi_contact_portfolio_choice_scenario(
    db_url: str,
    *,
    scenario_kind: str = "obvious",
) -> MultiContactPortfolioChoiceScenario:
    """Create a portfolio-agent weak-discovery choice scenario.

    The actor represents multiple marketing clients but has only one contact slot.
    Candidate weak-discovery contacts include principal-side opportunities, a
    same-side peer, and a broad connector. This scenario is for networking
    experiments that observe contact choice before negotiation opening.
    """
    if scenario_kind not in {"obvious", "marginal"}:
        raise ValueError("scenario_kind must be 'obvious' or 'marginal'")

    engine = create_engine(db_url)
    metadata.create_all(engine)
    field = "marketing"
    actor_agent_id = "client_portfolio_agent"
    represented_portfolio = (
        {
            "id": "client_lifecycle_marketer",
            "type": "client",
            "field": field,
            "summary": "Lifecycle email marketer seeking growth/lifecycle marketing roles; quick placement is important.",
            "priority": "quick placement in lifecycle or growth marketing",
        },
        {
            "id": "client_brand_designer",
            "type": "client",
            "field": field,
            "summary": "Brand designer seeking creative marketing work and portfolio-led opportunities.",
            "priority": "creative marketing fit over fastest placement",
        },
        {
            "id": "client_marketing_analyst",
            "type": "client",
            "field": field,
            "summary": "Marketing analyst with campaign reporting and attribution experience; open to growth analytics roles.",
            "priority": "analytics-heavy marketing role with growth path",
        },
    )
    if scenario_kind == "obvious":
        candidate_metadata = {
            "marketing_growth_principal_agent": {
                "represented_type": "principal",
                "represented_parties": [
                    {
                        "id": "principal_growth_marketing_role",
                        "type": "principal",
                        "field": field,
                        "summary": "Hiring lifecycle/growth marketer for email campaigns, attribution, and quick start.",
                    }
                ],
                "networking_note": "specific principal-side opening with direct lifecycle/growth fit",
            },
            "marketing_events_principal_agent": {
                "represented_type": "principal",
                "represented_parties": [
                    {
                        "id": "principal_events_role",
                        "type": "principal",
                        "field": field,
                        "summary": "Hiring events coordinator for onsite event logistics and vendor coordination.",
                    }
                ],
                "networking_note": "principal-side opportunity, but weaker fit for lifecycle/email and analytics clients",
            },
            "marketing_peer_client_agent": {
                "represented_type": "client",
                "represented_parties": [
                    {
                        "id": "peer_client_marketing_generalist",
                        "type": "client",
                        "field": field,
                        "summary": "Represents another marketing jobseeker; possible same-side lead sharing but no direct hiring opportunity.",
                    }
                ],
                "networking_note": "same-side peer contact with theoretical lead value",
            },
            "marketing_connector_agent": {
                "represented_type": "principal",
                "represented_parties": [
                    {
                        "id": "principal_fractional_marketing_connector",
                        "type": "principal",
                        "field": field,
                        "summary": "Broad marketing connector with several possible leads but no specific immediate opening in context.",
                    }
                ],
                "networking_note": "broad connector value, less specific than direct principal opening",
            },
        }
    else:
        candidate_metadata = {
            "marketing_growth_principal_agent": {
                "represented_type": "principal",
                "represented_parties": [
                    {
                        "id": "principal_growth_contract_role",
                        "type": "principal",
                        "field": field,
                        "summary": "Contract growth marketing role with email lifecycle work, but only a six-week project and uncertain extension.",
                    }
                ],
                "networking_note": "direct lifecycle fit but short-term and uncertain",
            },
            "marketing_analytics_principal_agent": {
                "represented_type": "principal",
                "represented_parties": [
                    {
                        "id": "principal_marketing_analytics_role",
                        "type": "principal",
                        "field": field,
                        "summary": "Hiring marketing analyst for attribution dashboards, campaign reporting, and growth experiments.",
                    }
                ],
                "networking_note": "strong fit for analyst client, less relevant for lifecycle or brand clients",
            },
            "marketing_peer_client_agent": {
                "represented_type": "client",
                "represented_parties": [
                    {
                        "id": "peer_client_senior_marketer",
                        "type": "client",
                        "field": field,
                        "summary": "Same-side senior marketer whose agent often exchanges overflow leads, but no principal-side opening is visible.",
                    }
                ],
                "networking_note": "same-side contact with possible lead-generation value but no immediate negotiation target",
            },
            "marketing_connector_agent": {
                "represented_type": "principal",
                "represented_parties": [
                    {
                        "id": "principal_marketing_connector",
                        "type": "principal",
                        "field": field,
                        "summary": "Connector representing several early-stage marketing needs across lifecycle, analytics, and brand, but details are incomplete.",
                    }
                ],
                "networking_note": "broad possible portfolio value with incomplete specifics",
            },
        }

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)
        weak_edges = SqlWeakDiscoveryEdgeRepository(connection)

        nodes.add(Node(actor_agent_id, NodeType.AGENT), display_name="Client Portfolio Agent")
        for party in represented_portfolio:
            represented_id = str(party["id"])
            nodes.add(Node(represented_id, NodeType.CLIENT), display_name=represented_id.replace("_", " ").title())
            representation_edges.add(RepresentationEdge(actor_agent_id, represented_id, NodeType.CLIENT, RepresentationState.ACTIVE))

        for candidate_agent_id, metadata_record in candidate_metadata.items():
            represented_type = str(metadata_record["represented_type"])
            node_type = NodeType.CLIENT if represented_type == "client" else NodeType.PRINCIPAL
            nodes.add(Node(candidate_agent_id, NodeType.AGENT), display_name=candidate_agent_id.replace("_", " ").title())
            for party in metadata_record["represented_parties"]:
                represented_id = str(party["id"])
                nodes.add(Node(represented_id, node_type), display_name=represented_id.replace("_", " ").title())
                representation_edges.add(RepresentationEdge(candidate_agent_id, represented_id, node_type, RepresentationState.ACTIVE))
            weak_edges.add(
                WeakDiscoveryEdge(
                    from_agent_id=actor_agent_id,
                    to_agent_id=candidate_agent_id,
                    field=field,
                    state=WeakDiscoveryState.AVAILABLE,
                    rationale={
                        "reason": "same_field_portfolio_candidate",
                        "field": field,
                        "target_represented_type": represented_type,
                        "target_represented_parties": metadata_record["represented_parties"],
                        "networking_note": metadata_record["networking_note"],
                    },
                )
            )

    return MultiContactPortfolioChoiceScenario(
        db_url=db_url,
        scenario_id=f"multi_contact_portfolio_choice_{scenario_kind}",
        actor_agent_id=actor_agent_id,
        field=field,
        contact_limit=1,
        represented_portfolio=represented_portfolio,
        candidate_agents=tuple(candidate_metadata),
        candidate_metadata=candidate_metadata,
    )


def seed_open_market_networking_scenario(db_url: str) -> OpenMarketNetworkingScenario:
    """Create a deterministic multi-industry open networking market.

    The market starts with weak discovery only. Each agent represents a small
    portfolio of clients or principals in one industry. This scenario is for
    observing weak discovery, contact formation, and negotiation-start behavior
    without adding new protocols or scoring match quality.
    """
    engine = create_engine(db_url)
    metadata.create_all(engine)
    agent_specs: dict[str, tuple[str, str, tuple[dict[str, object], ...]]] = {
        "marketing_client_agent_a": (
            "marketing",
            "client",
            (
                {"id": "client_lifecycle_marketer", "type": "client", "industry": "marketing", "credentials": ["email automation", "A/B testing"], "salary_expectation": 95000, "summary": "Lifecycle marketer seeking growth email role."},
                {"id": "client_brand_designer", "type": "client", "industry": "marketing", "credentials": ["brand systems", "campaign creative"], "salary_expectation": 90000, "summary": "Brand designer seeking creative marketing team."},
                {"id": "client_marketing_analyst", "type": "client", "industry": "marketing", "credentials": ["attribution", "dashboards"], "salary_expectation": 105000, "summary": "Marketing analyst seeking growth analytics role."},
            ),
        ),
        "marketing_client_agent_b": (
            "marketing",
            "client",
            (
                {"id": "client_events_manager", "type": "client", "industry": "marketing", "credentials": ["events", "vendor management"], "salary_expectation": 85000, "summary": "Events manager seeking field marketing role."},
                {"id": "client_content_strategist", "type": "client", "industry": "marketing", "credentials": ["SEO", "editorial calendar"], "salary_expectation": 92000, "summary": "Content strategist seeking B2B content role."},
                {"id": "client_growth_generalist", "type": "client", "industry": "marketing", "credentials": ["paid social", "landing pages"], "salary_expectation": 98000, "summary": "Growth generalist seeking startup marketing role."},
            ),
        ),
        "marketing_principal_agent_a": (
            "marketing",
            "principal",
            (
                {"id": "principal_growth_role", "type": "principal", "industry": "marketing", "salary_range": {"min": 90000, "max": 115000}, "requirements": ["email automation", "growth experiments"], "summary": "Hiring lifecycle growth marketer."},
                {"id": "principal_brand_role", "type": "principal", "industry": "marketing", "salary_range": {"min": 80000, "max": 100000}, "requirements": ["brand systems", "campaign creative"], "summary": "Hiring brand campaign designer."},
                {"id": "principal_content_role", "type": "principal", "industry": "marketing", "salary_range": {"min": 85000, "max": 105000}, "requirements": ["SEO", "B2B content"], "summary": "Hiring content strategist."},
            ),
        ),
        "software_client_agent_a": (
            "software",
            "client",
            (
                {"id": "client_backend_engineer", "type": "client", "industry": "software", "credentials": ["Python", "APIs"], "salary_expectation": 155000, "summary": "Backend engineer seeking platform role."},
                {"id": "client_frontend_engineer", "type": "client", "industry": "software", "credentials": ["React", "design systems"], "salary_expectation": 145000, "summary": "Frontend engineer seeking product team."},
                {"id": "client_data_engineer", "type": "client", "industry": "software", "credentials": ["Python", "ETL"], "salary_expectation": 150000, "summary": "Data engineer seeking pipeline work."},
            ),
        ),
        "software_client_agent_b": (
            "software",
            "client",
            (
                {"id": "client_ml_engineer", "type": "client", "industry": "software", "credentials": ["model deployment", "Python"], "salary_expectation": 175000, "summary": "ML engineer seeking production ML role."},
                {"id": "client_devops_engineer", "type": "client", "industry": "software", "credentials": ["Kubernetes", "CI/CD"], "salary_expectation": 160000, "summary": "DevOps engineer seeking infrastructure role."},
                {"id": "client_qa_automation", "type": "client", "industry": "software", "credentials": ["test automation", "Playwright"], "salary_expectation": 120000, "summary": "QA automation engineer seeking quality platform role."},
            ),
        ),
        "software_principal_agent_a": (
            "software",
            "principal",
            (
                {"id": "principal_backend_role", "type": "principal", "industry": "software", "salary_range": {"min": 140000, "max": 165000}, "requirements": ["Python", "API development"], "summary": "Hiring backend platform engineer."},
                {"id": "principal_data_role", "type": "principal", "industry": "software", "salary_range": {"min": 140000, "max": 170000}, "requirements": ["ETL", "warehouse modeling"], "summary": "Hiring data platform engineer."},
                {"id": "principal_infra_role", "type": "principal", "industry": "software", "salary_range": {"min": 150000, "max": 180000}, "requirements": ["Kubernetes", "reliability"], "summary": "Hiring infrastructure engineer."},
            ),
        ),
        "health_client_agent_a": (
            "healthcare_ops",
            "client",
            (
                {"id": "client_clinic_ops_manager", "type": "client", "industry": "healthcare_ops", "credentials": ["clinic scheduling", "staffing"], "salary_expectation": 90000, "summary": "Clinic operations manager seeking outpatient ops role."},
                {"id": "client_billing_specialist", "type": "client", "industry": "healthcare_ops", "credentials": ["claims", "revenue cycle"], "salary_expectation": 78000, "summary": "Billing specialist seeking revenue-cycle role."},
                {"id": "client_patient_success", "type": "client", "industry": "healthcare_ops", "credentials": ["patient support", "CRM"], "salary_expectation": 72000, "summary": "Patient success lead seeking care coordination role."},
            ),
        ),
        "health_principal_agent_a": (
            "healthcare_ops",
            "principal",
            (
                {"id": "principal_clinic_ops_role", "type": "principal", "industry": "healthcare_ops", "salary_range": {"min": 85000, "max": 105000}, "requirements": ["clinic scheduling", "staffing"], "summary": "Hiring outpatient clinic ops manager."},
                {"id": "principal_revenue_cycle_role", "type": "principal", "industry": "healthcare_ops", "salary_range": {"min": 70000, "max": 90000}, "requirements": ["claims", "denials"], "summary": "Hiring revenue-cycle specialist."},
                {"id": "principal_care_coordination_role", "type": "principal", "industry": "healthcare_ops", "salary_range": {"min": 65000, "max": 82000}, "requirements": ["patient support", "care coordination"], "summary": "Hiring care coordination lead."},
            ),
        ),
        "finance_client_agent_a": (
            "finance_admin",
            "client",
            (
                {"id": "client_bookkeeper", "type": "client", "industry": "finance_admin", "credentials": ["QuickBooks", "AP/AR"], "salary_expectation": 70000, "summary": "Bookkeeper seeking small-business accounting role."},
                {"id": "client_financial_analyst", "type": "client", "industry": "finance_admin", "credentials": ["Excel", "forecasting"], "salary_expectation": 95000, "summary": "Financial analyst seeking FP&A role."},
                {"id": "client_operations_coordinator", "type": "client", "industry": "finance_admin", "credentials": ["vendor management", "office ops"], "salary_expectation": 68000, "summary": "Operations coordinator seeking admin ops role."},
            ),
        ),
        "finance_principal_agent_a": (
            "finance_admin",
            "principal",
            (
                {"id": "principal_bookkeeping_role", "type": "principal", "industry": "finance_admin", "salary_range": {"min": 65000, "max": 78000}, "requirements": ["QuickBooks", "AP/AR"], "summary": "Hiring bookkeeper."},
                {"id": "principal_fpa_role", "type": "principal", "industry": "finance_admin", "salary_range": {"min": 90000, "max": 115000}, "requirements": ["forecasting", "Excel"], "summary": "Hiring FP&A analyst."},
                {"id": "principal_admin_ops_role", "type": "principal", "industry": "finance_admin", "salary_range": {"min": 60000, "max": 76000}, "requirements": ["vendor management", "office ops"], "summary": "Hiring admin operations coordinator."},
            ),
        ),
        "cross_industry_connector_agent": (
            "marketing",
            "principal",
            (
                {"id": "principal_fractional_marketing_need", "type": "principal", "industry": "marketing", "salary_range": {"min": 75000, "max": 120000}, "requirements": ["marketing generalist", "startup context"], "summary": "Connector with several fractional marketing leads but incomplete details."},
                {"id": "principal_growth_advisor_need", "type": "principal", "industry": "marketing", "salary_range": {"min": 90000, "max": 130000}, "requirements": ["growth strategy", "analytics"], "summary": "Connector with possible growth advisor need."},
                {"id": "principal_brand_project_need", "type": "principal", "industry": "marketing", "salary_range": {"min": 70000, "max": 95000}, "requirements": ["brand refresh", "campaigns"], "summary": "Connector with possible brand project."},
            ),
        ),
        "software_connector_agent": (
            "software",
            "principal",
            (
                {"id": "principal_fractional_backend_need", "type": "principal", "industry": "software", "salary_range": {"min": 130000, "max": 170000}, "requirements": ["APIs", "startup backend"], "summary": "Connector with fractional backend leads."},
                {"id": "principal_ai_tooling_need", "type": "principal", "industry": "software", "salary_range": {"min": 150000, "max": 190000}, "requirements": ["Python", "ML tooling"], "summary": "Connector with early AI tooling need."},
                {"id": "principal_quality_platform_need", "type": "principal", "industry": "software", "salary_range": {"min": 110000, "max": 135000}, "requirements": ["test automation", "CI"], "summary": "Connector with quality platform lead."},
            ),
        ),
    }

    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        representation_edges = SqlRepresentationEdgeRepository(connection)
        weak_edges = SqlWeakDiscoveryEdgeRepository(connection)
        for agent_id, (_field, represented_type, portfolio) in agent_specs.items():
            nodes.add(Node(agent_id, NodeType.AGENT), display_name=agent_id.replace("_", " ").title())
            node_type = NodeType.CLIENT if represented_type == "client" else NodeType.PRINCIPAL
            for party in portfolio:
                represented_id = str(party["id"])
                nodes.add(Node(represented_id, node_type), display_name=represented_id.replace("_", " ").title())
                representation_edges.add(RepresentationEdge(agent_id, represented_id, node_type, RepresentationState.ACTIVE))
        for from_agent_id, (from_field, _from_type, _from_portfolio) in agent_specs.items():
            for to_agent_id, (to_field, to_type, to_portfolio) in agent_specs.items():
                if from_agent_id == to_agent_id or from_field != to_field:
                    continue
                weak_edges.add(
                    WeakDiscoveryEdge(
                        from_agent_id=from_agent_id,
                        to_agent_id=to_agent_id,
                        field=from_field,
                        state=WeakDiscoveryState.AVAILABLE,
                        rationale={
                            "reason": "same_industry_open_market",
                            "field": from_field,
                            "target_represented_type": to_type,
                            "target_represented_parties": to_portfolio,
                        },
                    )
                )

    return OpenMarketNetworkingScenario(
        db_url=db_url,
        scenario_id="open_market_networking_v1",
        agent_fields={agent_id: spec[0] for agent_id, spec in agent_specs.items()},
        represented_types={agent_id: spec[1] for agent_id, spec in agent_specs.items()},
        represented_portfolios={agent_id: spec[2] for agent_id, spec in agent_specs.items()},
    )


def _pairwise_fact_profiles_by_agent() -> dict[str, list[RepresentedPartyProfile]]:
    return {
        "client_agent": [
            RepresentedPartyProfile(
                represented_party_id="client",
                represented_party_type="client",
                facts={
                    "salary_range": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Desired salary range",
                        value={"min": 140000, "max": 170000, "currency": "USD"},
                    ),
                    "credentials": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Provable credentials",
                        value={"education": ["BS Computer Science"], "certifications": ["AWS Developer Associate"]},
                    ),
                    "benefits": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Desired benefits",
                        value=["health insurance", "401k match", "remote work support"],
                    ),
                    "employment_type": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Acceptable employment types",
                        value=["salaried W-2"],
                    ),
                    "disposition": RepresentedPartyFact(
                        kind=FactKind.EVIDENCE,
                        label="Working style and interests",
                        value={"working_style": ["independent", "mentors junior engineers"], "interests": ["API design", "data reliability"]},
                    ),
                    "career_path": RepresentedPartyFact(
                        kind=FactKind.EVIDENCE,
                        label="Desired career path",
                        value={"trajectory": "senior backend IC to staff engineer", "growth_interests": ["technical leadership", "system design"]},
                    ),
                },
                priorities=(
                    {"field": "salary_range", "rank": 1, "importance": "hard"},
                    {"field": "employment_type", "rank": 2, "importance": "hard"},
                    {"field": "career_path", "rank": 3, "importance": "strong"},
                ),
            )
        ],
        "principal_agent": [
            RepresentedPartyProfile(
                represented_party_id="principal",
                represented_party_type="principal",
                facts={
                    "salary_range": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Offered salary range",
                        value={"min": 130000, "max": 160000, "currency": "USD"},
                    ),
                    "credentials": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Required credentials",
                        value={"education": ["BS Computer Science or equivalent experience"], "certifications": []},
                    ),
                    "benefits": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Offered benefits",
                        value=["health insurance", "401k match", "remote work support"],
                    ),
                    "employment_type": RepresentedPartyFact(
                        kind=FactKind.CONSTRAINT,
                        label="Offered employment type",
                        value=["salaried W-2"],
                    ),
                    "disposition": RepresentedPartyFact(
                        kind=FactKind.EVIDENCE,
                        label="Desired working style",
                        value={"working_style": ["independent", "comfortable mentoring"], "team_context": "small platform team with high ownership"},
                    ),
                    "career_path": RepresentedPartyFact(
                        kind=FactKind.EVIDENCE,
                        label="Expected growth path",
                        value={"trajectory": "backend engineer to technical lead", "growth_support": ["architecture ownership", "mentoring opportunities"]},
                    ),
                },
                priorities=(
                    {"field": "credentials", "rank": 1, "importance": "hard"},
                    {"field": "employment_type", "rank": 2, "importance": "hard"},
                    {"field": "disposition", "rank": 3, "importance": "strong"},
                ),
            )
        ],
    }


def _market_role(client_index: int, principal_index: int) -> str:
    roles = ["backend engineer", "data engineer", "platform engineer", "frontend engineer", "ml engineer"]
    return roles[(client_index + principal_index) % len(roles)]
