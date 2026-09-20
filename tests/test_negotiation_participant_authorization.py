from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

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

    def list_for_negotiation(self, negotiation_id: str) -> list[ProtocolEvent]:
        return [event for event in self.records if event.negotiation_id == negotiation_id]


def make_service(
    negotiations: InMemoryNegotiations,
    events: InMemoryEvents,
) -> NegotiationService:
    return NegotiationService(
        connections=UnusedConnections(),
        negotiations=negotiations,
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 6, tzinfo=timezone.utc),
    )


def make_negotiations(state: NegotiationState) -> InMemoryNegotiations:
    return InMemoryNegotiations(
        {
            "negotiation_1": Negotiation(
                id="negotiation_1",
                from_agent_id="agent_1",
                to_agent_id="agent_2",
                state=state,
                subject={"role": "engineer"},
            )
        }
    )


def assert_rejected_without_mutation(
    negotiations: InMemoryNegotiations,
    events: InMemoryEvents,
    expected_state: NegotiationState,
) -> None:
    assert negotiations.records["negotiation_1"].state == expected_state
    assert negotiations.saved == []
    assert events.records == []


def test_non_participant_cannot_respond_to_negotiation() -> None:
    """Protects INV-N-007."""
    negotiations = make_negotiations(NegotiationState.REQUESTED)
    events = InMemoryEvents()
    service = make_service(negotiations, events)

    with pytest.raises(PermissionError):
        service.respond_to_negotiation(
            negotiation_id="negotiation_1",
            actor_agent_id="agent_3",
            decision=NegotiationDecision.ACCEPT,
        )

    assert_rejected_without_mutation(negotiations, events, NegotiationState.REQUESTED)


def test_non_participant_cannot_send_message() -> None:
    """Protects INV-N-007."""
    negotiations = make_negotiations(NegotiationState.OPEN)
    events = InMemoryEvents()
    service = make_service(negotiations, events)

    with pytest.raises(PermissionError):
        service.send_message(
            negotiation_id="negotiation_1",
            actor_agent_id="agent_3",
            body="Unauthorized message.",
        )

    assert_rejected_without_mutation(negotiations, events, NegotiationState.OPEN)


def test_non_participant_cannot_propose_match() -> None:
    """Protects INV-N-007."""
    negotiations = make_negotiations(NegotiationState.OPEN)
    events = InMemoryEvents()
    service = make_service(negotiations, events)

    with pytest.raises(PermissionError):
        service.propose_match(
            negotiation_id="negotiation_1",
            actor_agent_id="agent_3",
            proposal={"candidate_id": "client_1", "principal_id": "principal_1"},
        )

    assert_rejected_without_mutation(negotiations, events, NegotiationState.OPEN)


def test_non_participant_cannot_accept_match() -> None:
    """Protects INV-N-007."""
    negotiations = make_negotiations(NegotiationState.OPEN)
    events = InMemoryEvents(
        [
            ProtocolEvent(
                type=ProtocolEventType.MATCH_PROPOSED,
                actor_agent_id="agent_1",
                negotiation_id="negotiation_1",
                occurred_at=datetime(2026, 1, 6, tzinfo=timezone.utc),
                payload={"proposal": {}},
            )
        ]
    )
    service = make_service(negotiations, events)

    with pytest.raises(PermissionError):
        service.accept_match(negotiation_id="negotiation_1", actor_agent_id="agent_3")

    assert negotiations.records["negotiation_1"].state == NegotiationState.OPEN
    assert negotiations.saved == []
    assert [event.type for event in events.records] == [ProtocolEventType.MATCH_PROPOSED]


def test_non_participant_cannot_close_negotiation() -> None:
    """Protects INV-N-007."""
    negotiations = make_negotiations(NegotiationState.OPEN)
    events = InMemoryEvents()
    service = make_service(negotiations, events)

    with pytest.raises(PermissionError):
        service.close_negotiation(
            negotiation_id="negotiation_1",
            actor_agent_id="agent_3",
            reason="unauthorized",
        )

    assert_rejected_without_mutation(negotiations, events, NegotiationState.OPEN)
