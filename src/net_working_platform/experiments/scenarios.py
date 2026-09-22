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
