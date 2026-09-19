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

    def list_for_negotiation(self, negotiation_id: str) -> list[ProtocolEvent]:
        return [event for event in self.records if event.negotiation_id == negotiation_id]


def make_service(
    negotiations: InMemoryNegotiations,
    events: InMemoryEvents,
    now: datetime = datetime(2026, 1, 5, tzinfo=timezone.utc),
) -> NegotiationService:
    return NegotiationService(
        connections=UnusedConnections(),
        negotiations=negotiations,
        events=events,
        new_id=lambda: "unused",
        now=lambda: now,
    )


def test_propose_match_service_appends_event_for_open_negotiation() -> None:
    """Protects INV-N-005 and INV-H-001."""
    events = InMemoryEvents()
    service = make_service(
        InMemoryNegotiations(
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
        events,
    )

    service.propose_match(
        negotiation_id="negotiation_1",
        actor_agent_id="agent_1",
        proposal={"candidate_id": "client_1", "principal_id": "principal_1"},
    )

    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.MATCH_PROPOSED,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            payload={"proposal": {"candidate_id": "client_1", "principal_id": "principal_1"}},
        )
    ]


def test_accept_match_service_requires_prior_proposal() -> None:
    """Protects INV-N-005."""
    service = make_service(
        InMemoryNegotiations(
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
        InMemoryEvents(),
    )

    with pytest.raises(ProtocolViolation):
        service.accept_match(negotiation_id="negotiation_1", actor_agent_id="agent_2")


def test_accept_match_service_marks_negotiation_matched() -> None:
    """Protects INV-N-005 and INV-H-001."""
    negotiations = InMemoryNegotiations(
        {
            "negotiation_1": Negotiation(
                id="negotiation_1",
                from_agent_id="agent_1",
                to_agent_id="agent_2",
                state=NegotiationState.OPEN,
                subject={},
            )
        }
    )
    events = InMemoryEvents(
        [
            ProtocolEvent(
                type=ProtocolEventType.MATCH_PROPOSED,
                actor_agent_id="agent_1",
                negotiation_id="negotiation_1",
                occurred_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
                payload={"proposal": {}},
            )
        ]
    )
    service = make_service(negotiations, events)

    negotiation = service.accept_match(negotiation_id="negotiation_1", actor_agent_id="agent_2")

    assert negotiation.state == NegotiationState.MATCHED
    assert negotiations.saved == [negotiation]
    assert events.records[-1] == ProtocolEvent(
        type=ProtocolEventType.MATCH_ACCEPTED,
        actor_agent_id="agent_2",
        negotiation_id="negotiation_1",
        occurred_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        payload={},
    )


def test_close_negotiation_service_closes_open_negotiation() -> None:
    """Protects INV-N-006 and INV-H-001."""
    negotiations = InMemoryNegotiations(
        {
            "negotiation_1": Negotiation(
                id="negotiation_1",
                from_agent_id="agent_1",
                to_agent_id="agent_2",
                state=NegotiationState.OPEN,
                subject={},
            )
        }
    )
    events = InMemoryEvents()
    service = make_service(negotiations, events)

    negotiation = service.close_negotiation(
        negotiation_id="negotiation_1",
        actor_agent_id="agent_1",
        reason="no_longer_relevant",
    )

    assert negotiation.state == NegotiationState.CLOSED
    assert negotiations.saved == [negotiation]
    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.CLOSE_NEGOTIATION,
            actor_agent_id="agent_1",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            payload={"reason": "no_longer_relevant"},
        )
    ]


def test_retrieve_negotiation_history_returns_structured_events() -> None:
    """Protects INV-H-003."""
    event = ProtocolEvent(
        type=ProtocolEventType.MESSAGE,
        actor_agent_id="agent_1",
        negotiation_id="negotiation_1",
        occurred_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        payload={"body": "Still interested."},
    )
    service = make_service(InMemoryNegotiations({}), InMemoryEvents([event]))

    assert service.get_negotiation_history("negotiation_1") == [event]
