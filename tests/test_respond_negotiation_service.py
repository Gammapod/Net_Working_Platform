from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from net_working_platform.application.negotiations import NegotiationService
from net_working_platform.domain.model import (
    AgentConnection,
    Negotiation,
    NegotiationDecision,
    NegotiationState,
    ProtocolEvent,
    ProtocolEventType,
)


@dataclass
class UnusedConnections:
    def get_between(self, from_agent_id: str, to_agent_id: str) -> AgentConnection | None:
        return None


@dataclass
class InMemoryNegotiations:
    records: dict[str, Negotiation]
    saved: list[Negotiation] = field(default_factory=list)

    def count_open_for_agent(self, agent_id: str) -> int:
        return 0

    def add(self, negotiation: Negotiation) -> None:
        self.records[negotiation.id] = negotiation

    def get(self, negotiation_id: str) -> Negotiation:
        return self.records[negotiation_id]

    def save(self, negotiation: Negotiation) -> None:
        self.records[negotiation.id] = negotiation
        self.saved.append(negotiation)


@dataclass
class InMemoryEvents:
    records: list[ProtocolEvent] = field(default_factory=list)

    def append(self, event: ProtocolEvent) -> None:
        self.records.append(event)


def test_accept_negotiation_service_opens_requested_negotiation() -> None:
    """Protects INV-N-003 and INV-H-001."""
    negotiations = InMemoryNegotiations(
        {
            "negotiation_1": Negotiation(
                id="negotiation_1",
                from_agent_id="agent_1",
                to_agent_id="agent_2",
                state=NegotiationState.REQUESTED,
                subject={},
            )
        }
    )
    events = InMemoryEvents()
    service = NegotiationService(
        connections=UnusedConnections(),
        negotiations=negotiations,
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    negotiation = service.respond_to_negotiation(
        negotiation_id="negotiation_1",
        actor_agent_id="agent_2",
        decision=NegotiationDecision.ACCEPT,
    )

    assert negotiation.state == NegotiationState.OPEN
    assert negotiations.saved == [negotiation]
    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
            actor_agent_id="agent_2",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            payload={"decision": "accept"},
        )
    ]


def test_reject_negotiation_service_closes_requested_negotiation() -> None:
    """Protects INV-N-003 and INV-H-001."""
    negotiations = InMemoryNegotiations(
        {
            "negotiation_1": Negotiation(
                id="negotiation_1",
                from_agent_id="agent_1",
                to_agent_id="agent_2",
                state=NegotiationState.REQUESTED,
                subject={},
            )
        }
    )
    events = InMemoryEvents()
    service = NegotiationService(
        connections=UnusedConnections(),
        negotiations=negotiations,
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    negotiation = service.respond_to_negotiation(
        negotiation_id="negotiation_1",
        actor_agent_id="agent_2",
        decision=NegotiationDecision.REJECT,
    )

    assert negotiation.state == NegotiationState.CLOSED
    assert negotiations.saved == [negotiation]
    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
            actor_agent_id="agent_2",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            payload={"decision": "reject"},
        )
    ]
