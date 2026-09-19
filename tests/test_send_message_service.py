from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from net_working_platform.application.negotiations import NegotiationService
from net_working_platform.domain.model import (
    AgentConnection,
    Negotiation,
    NegotiationState,
    ProtocolEvent,
    ProtocolEventType,
    ProtocolViolation,
)


@dataclass
class UnusedConnections:
    def get_between(self, from_agent_id: str, to_agent_id: str) -> AgentConnection | None:
        return None


@dataclass
class InMemoryNegotiations:
    records: dict[str, Negotiation]

    def count_open_for_agent(self, agent_id: str) -> int:
        return 0

    def add(self, negotiation: Negotiation) -> None:
        self.records[negotiation.id] = negotiation

    def get(self, negotiation_id: str) -> Negotiation:
        return self.records[negotiation_id]

    def save(self, negotiation: Negotiation) -> None:
        self.records[negotiation.id] = negotiation


@dataclass
class InMemoryEvents:
    records: list[ProtocolEvent] = field(default_factory=list)

    def append(self, event: ProtocolEvent) -> None:
        self.records.append(event)


def test_send_message_service_appends_message_event_for_open_negotiation() -> None:
    """Protects INV-N-004 and INV-H-001."""
    events = InMemoryEvents()
    service = NegotiationService(
        connections=UnusedConnections(),
        negotiations=InMemoryNegotiations(
            {
                "negotiation_1": Negotiation(
                    id="negotiation_1",
                    from_agent_id="agent_1",
                    to_agent_id="agent_2",
                    state=NegotiationState.OPEN,
                    subject={},
                )
            }
        ),
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 4, tzinfo=timezone.utc),
    )

    service.send_message(
        negotiation_id="negotiation_1",
        actor_agent_id="agent_1",
        body="Candidate is available Tuesday.",
    )

    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.MESSAGE,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
            payload={"body": "Candidate is available Tuesday."},
        )
    ]


def test_send_message_service_rejects_non_open_negotiation() -> None:
    """Protects INV-N-004."""
    events = InMemoryEvents()
    service = NegotiationService(
        connections=UnusedConnections(),
        negotiations=InMemoryNegotiations(
            {
                "negotiation_1": Negotiation(
                    id="negotiation_1",
                    from_agent_id="agent_1",
                    to_agent_id="agent_2",
                    state=NegotiationState.REQUESTED,
                    subject={},
                )
            }
        ),
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(ProtocolViolation):
        service.send_message(
            negotiation_id="negotiation_1",
            actor_agent_id="agent_1",
            body="Too early.",
        )

    assert events.records == []
