from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from net_working_platform.application.negotiations import NegotiationService
from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    CapacityLimitExceeded,
    Negotiation,
    NegotiationState,
    ProtocolEvent,
    ProtocolEventType,
)


@dataclass
class InMemoryAgentConnections:
    connections: dict[tuple[str, str], AgentConnection] = field(default_factory=dict)

    def get_between(self, from_agent_id: str, to_agent_id: str) -> AgentConnection | None:
        return self.connections.get((from_agent_id, to_agent_id))


@dataclass
class InMemoryNegotiations:
    records: list[Negotiation] = field(default_factory=list)
    open_count: int = 0

    def count_open_for_agent(self, agent_id: str) -> int:
        return self.open_count

    def add(self, negotiation: Negotiation) -> None:
        self.records.append(negotiation)


@dataclass
class InMemoryEvents:
    records: list[ProtocolEvent] = field(default_factory=list)

    def append(self, event: ProtocolEvent) -> None:
        self.records.append(event)


def test_request_negotiation_service_creates_record_and_event() -> None:
    """Protects INV-N-001, INV-N-002, and INV-H-001."""
    connections = InMemoryAgentConnections(
        {("agent_1", "agent_2"): AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE)}
    )
    negotiations = InMemoryNegotiations()
    events = InMemoryEvents()
    service = NegotiationService(
        connections=connections,
        negotiations=negotiations,
        events=events,
        new_id=lambda: "negotiation_1",
        now=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    negotiation = service.request_negotiation(
        from_agent_id="agent_1",
        to_agent_id="agent_2",
        subject={"role": "engineer"},
        max_open_negotiations=2,
    )

    assert negotiation == Negotiation(
        id="negotiation_1",
        from_agent_id="agent_1",
        to_agent_id="agent_2",
        state=NegotiationState.REQUESTED,
        subject={"role": "engineer"},
    )
    assert negotiations.records == [negotiation]
    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            payload={"to_agent_id": "agent_2", "subject": {"role": "engineer"}},
        )
    ]


def test_request_negotiation_service_requires_active_connection() -> None:
    """Protects INV-G-001."""
    service = NegotiationService(
        connections=InMemoryAgentConnections(
            {("agent_1", "agent_2"): AgentConnection("agent_1", "agent_2", AgentConnectionState.INACTIVE)}
        ),
        negotiations=InMemoryNegotiations(),
        events=InMemoryEvents(),
        new_id=lambda: "negotiation_1",
        now=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(PermissionError):
        service.request_negotiation(
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            subject={},
            max_open_negotiations=2,
        )


def test_request_negotiation_service_rejects_when_actor_at_capacity() -> None:
    """Protects INV-C-001 and INV-C-002."""
    events = InMemoryEvents()
    service = NegotiationService(
        connections=InMemoryAgentConnections(
            {("agent_1", "agent_2"): AgentConnection("agent_1", "agent_2", AgentConnectionState.ACTIVE)}
        ),
        negotiations=InMemoryNegotiations(open_count=2),
        events=events,
        new_id=lambda: "negotiation_1",
        now=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(CapacityLimitExceeded):
        service.request_negotiation(
            from_agent_id="agent_1",
            to_agent_id="agent_2",
            subject={},
            max_open_negotiations=2,
        )

    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
            actor_agent_id="agent_1",
            negotiation_id=None,
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            payload={"to_agent_id": "agent_2", "rejected": True, "reason": "capacity_limit"},
        )
    ]
