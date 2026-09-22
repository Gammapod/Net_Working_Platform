from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from net_working_platform.application.discovery import DiscoveryService
from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    ProtocolEvent,
    ProtocolEventType,
    WeakDiscoveryEdge,
    WeakDiscoveryState,
)


@dataclass
class InMemoryAgentConnections:
    records: dict[tuple[str, str], AgentConnection] = field(default_factory=dict)

    def add(self, connection: AgentConnection) -> None:
        self.records[(connection.from_agent_id, connection.to_agent_id)] = connection

    def get_between(self, from_agent_id: str, to_agent_id: str) -> AgentConnection | None:
        return self.records.get((from_agent_id, to_agent_id))

    def count_active_from_agent(self, agent_id: str) -> int:
        return sum(1 for connection in self.records.values() if connection.from_agent_id == agent_id and connection.state == AgentConnectionState.ACTIVE)


@dataclass
class InMemoryWeakDiscoveryEdges:
    records: list[WeakDiscoveryEdge]

    def get(self, from_agent_id: str, to_agent_id: str, field: str) -> WeakDiscoveryEdge | None:
        return next(
            (
                edge
                for edge in self.records
                if edge.from_agent_id == from_agent_id
                and edge.to_agent_id == to_agent_id
                and edge.field == field
            ),
            None,
        )

    def list_available_for_agent(self, agent_id: str) -> list[WeakDiscoveryEdge]:
        return [
            edge
            for edge in self.records
            if edge.from_agent_id == agent_id and edge.state == WeakDiscoveryState.AVAILABLE
        ]


@dataclass
class InMemoryEvents:
    records: list[ProtocolEvent] = field(default_factory=list)

    def append(self, event: ProtocolEvent) -> None:
        self.records.append(event)


def make_service(
    *,
    edges: list[WeakDiscoveryEdge],
    connections: InMemoryAgentConnections | None = None,
    events: InMemoryEvents | None = None,
) -> tuple[DiscoveryService, InMemoryAgentConnections, InMemoryEvents]:
    connection_repo = connections or InMemoryAgentConnections()
    event_repo = events or InMemoryEvents()
    return (
        DiscoveryService(
            agent_connections=connection_repo,
            weak_discovery_edges=InMemoryWeakDiscoveryEdges(edges),
            events=event_repo,
            now=lambda: datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc),
        ),
        connection_repo,
        event_repo,
    )


def test_list_discoverable_agents_filters_weak_edges_by_field() -> None:
    """Protects INV-D-001."""
    service, _, _ = make_service(
        edges=[
            WeakDiscoveryEdge("marketing_client_agent_1", "marketing_principal_agent", "marketing", WeakDiscoveryState.AVAILABLE, {"reason": "same_field"}),
            WeakDiscoveryEdge("marketing_client_agent_1", "marketing_client_agent_2", "marketing", WeakDiscoveryState.AVAILABLE, {"reason": "same_field"}),
            WeakDiscoveryEdge("marketing_client_agent_1", "programming_principal_agent", "programming", WeakDiscoveryState.AVAILABLE, {"reason": "different_field"}),
        ]
    )

    assert service.list_discoverable_agents(actor_agent_id="marketing_client_agent_1", field="marketing") == [
        {
            "agent_id": "marketing_principal_agent",
            "field": "marketing",
            "rationale": {"reason": "same_field"},
        },
        {
            "agent_id": "marketing_client_agent_2",
            "field": "marketing",
            "rationale": {"reason": "same_field"},
        },
    ]


def test_probe_weak_connection_requires_matching_weak_edge() -> None:
    """Protects INV-D-001 and INV-D-002."""
    service, _, events = make_service(
        edges=[
            WeakDiscoveryEdge("marketing_client_agent_1", "marketing_principal_agent", "marketing", WeakDiscoveryState.AVAILABLE, {}),
        ]
    )

    service.probe_weak_connection(
        actor_agent_id="marketing_client_agent_1",
        target_agent_id="marketing_principal_agent",
        field="marketing",
        criteria={"role_field": "marketing"},
    )

    with pytest.raises(PermissionError):
        service.probe_weak_connection(
            actor_agent_id="marketing_client_agent_1",
            target_agent_id="programming_principal_agent",
            field="marketing",
            criteria={"role_field": "marketing"},
        )

    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.WEAK_CONNECTION_PROBED,
            actor_agent_id="marketing_client_agent_1",
            negotiation_id=None,
            occurred_at=datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc),
            payload={
                "target_agent_id": "marketing_principal_agent",
                "field": "marketing",
                "criteria": {"role_field": "marketing"},
            },
        )
    ]


def test_request_contact_requires_matching_weak_edge_and_creates_active_connection() -> None:
    """Protects INV-D-002 and INV-G-001."""
    service, connections, events = make_service(
        edges=[
            WeakDiscoveryEdge("marketing_client_agent_1", "marketing_principal_agent", "marketing", WeakDiscoveryState.AVAILABLE, {}),
        ]
    )

    connection = service.request_contact(
        actor_agent_id="marketing_client_agent_1",
        target_agent_id="marketing_principal_agent",
        field="marketing",
        reason="Client is seeking marketing roles.",
    )

    assert connection == AgentConnection(
        "marketing_client_agent_1",
        "marketing_principal_agent",
        AgentConnectionState.ACTIVE,
    )
    assert connections.get_between("marketing_client_agent_1", "marketing_principal_agent") == connection
    with pytest.raises(PermissionError):
        service.request_contact(
            actor_agent_id="marketing_client_agent_1",
            target_agent_id="programming_principal_agent",
            field="marketing",
            reason="Should not cross fields without a weak edge.",
        )
    assert [event.type for event in events.records] == [ProtocolEventType.CONTACT_REQUESTED]


def test_request_contact_rejects_actor_over_contact_limit() -> None:
    """Protects INV-D-003."""
    existing = InMemoryAgentConnections(
        {
            ("agent_1", "agent_2"): AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE),
            ("agent_1", "agent_3"): AgentConnection("agent_1", "agent_3", AgentConnectionState.ACTIVE),
            ("agent_1", "agent_4"): AgentConnection("agent_1", "agent_4", AgentConnectionState.ACTIVE),
        }
    )
    service, _, events = make_service(
        connections=existing,
        edges=[WeakDiscoveryEdge("agent_1", "agent_5", "marketing", WeakDiscoveryState.AVAILABLE, {})],
    )

    with pytest.raises(Exception, match="contact limit"):
        service.request_contact(
            actor_agent_id="agent_1",
            target_agent_id="agent_5",
            field="marketing",
            reason="too many contacts",
        )

    assert events.records == []
