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

    def list_for_negotiation(self, negotiation_id: str) -> list[ProtocolEvent]:
        return [event for event in self.records if event.negotiation_id == negotiation_id]


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


def test_send_message_service_reopens_proposal_pending_negotiation() -> None:
    """Protects INV-N-004, INV-N-009, and INV-H-001."""
    events = InMemoryEvents()
    negotiations = InMemoryNegotiations(
        {
            "negotiation_1": Negotiation(
                id="negotiation_1",
                from_agent_id="agent_1",
                to_agent_id="agent_2",
                state=NegotiationState.PROPOSAL_PENDING,
                subject={},
            )
        }
    )
    service = NegotiationService(
        connections=UnusedConnections(),
        negotiations=negotiations,
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 4, tzinfo=timezone.utc),
    )

    service.send_message(
        negotiation_id="negotiation_1",
        actor_agent_id="agent_2",
        body="Can you clarify the offer?",
    )

    assert negotiations.records["negotiation_1"].state == NegotiationState.OPEN
    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.MESSAGE,
            actor_agent_id="agent_2",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
            payload={"body": "Can you clarify the offer?"},
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


def test_send_message_service_rejects_message_after_actor_quota_used() -> None:
    """Protects INV-N-008."""
    prior_messages = [
        ProtocolEvent(
            type=ProtocolEventType.MESSAGE,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 4, index, tzinfo=timezone.utc),
            payload={"body": f"message {index}"},
        )
        for index in range(1, 4)
    ]
    events = InMemoryEvents(prior_messages.copy())
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
        now=lambda: datetime(2026, 1, 4, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(ProtocolViolation, match="message quota"):
        service.send_message(
            negotiation_id="negotiation_1",
            actor_agent_id="agent_1",
            body="one too many",
        )

    assert events.records == prior_messages


def test_message_quota_is_per_actor_per_negotiation() -> None:
    """Protects INV-N-008."""
    prior_messages = [
        ProtocolEvent(
            type=ProtocolEventType.MESSAGE,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 4, index, tzinfo=timezone.utc),
            payload={"body": f"agent 1 message {index}"},
        )
        for index in range(1, 4)
    ]
    events = InMemoryEvents(prior_messages.copy())
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
                ),
                "negotiation_2": Negotiation(
                    id="negotiation_2",
                    from_agent_id="agent_1",
                    to_agent_id="agent_2",
                    state=NegotiationState.OPEN,
                    subject={},
                ),
            }
        ),
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 4, 4, tzinfo=timezone.utc),
    )

    service.send_message(negotiation_id="negotiation_1", actor_agent_id="agent_2", body="other actor allowed")
    service.send_message(negotiation_id="negotiation_2", actor_agent_id="agent_1", body="other negotiation allowed")

    assert events.records[-2:] == [
        ProtocolEvent(
            type=ProtocolEventType.MESSAGE,
            actor_agent_id="agent_2",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 4, 4, tzinfo=timezone.utc),
            payload={"body": "other actor allowed"},
        ),
        ProtocolEvent(
            type=ProtocolEventType.MESSAGE,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_2",
            occurred_at=datetime(2026, 1, 4, 4, tzinfo=timezone.utc),
            payload={"body": "other negotiation allowed"},
        ),
    ]
