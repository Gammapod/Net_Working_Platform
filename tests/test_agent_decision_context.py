from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from net_working_platform.application.negotiations import NegotiationService
from net_working_platform.domain.model import (
    AgentConnection,
    Negotiation,
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
    records: list[Negotiation]
    add_called: bool = False
    save_called: bool = False

    def count_open_for_agent(self, agent_id: str) -> int:
        return len(
            [
                negotiation
                for negotiation in self.records
                if agent_id in {negotiation.from_agent_id, negotiation.to_agent_id}
                and negotiation.state in {NegotiationState.REQUESTED, NegotiationState.OPEN}
            ]
        )

    def list_active_for_agent(self, agent_id: str) -> list[Negotiation]:
        return [
            negotiation
            for negotiation in self.records
            if agent_id in {negotiation.from_agent_id, negotiation.to_agent_id}
            and negotiation.state in {NegotiationState.REQUESTED, NegotiationState.OPEN}
        ]

    def add(self, negotiation: Negotiation) -> None:
        self.add_called = True

    def get(self, negotiation_id: str) -> Negotiation:
        raise KeyError(negotiation_id)

    def save(self, negotiation: Negotiation) -> None:
        self.save_called = True


@dataclass
class InMemoryEvents:
    records: list[ProtocolEvent] = field(default_factory=list)
    append_called: bool = False

    def append(self, event: ProtocolEvent) -> None:
        self.append_called = True

    def list_for_negotiation(self, negotiation_id: str) -> list[ProtocolEvent]:
        return [event for event in self.records if event.negotiation_id == negotiation_id]

    def list_recent_for_agent(self, agent_id: str, negotiation_ids: list[str], limit: int) -> list[ProtocolEvent]:
        del agent_id
        return [event for event in self.records if event.negotiation_id in negotiation_ids][-limit:]


def test_get_agent_decision_context_returns_structured_read_only_context() -> None:
    """Protects INV-H-004."""
    negotiations = InMemoryNegotiations(
        [
            Negotiation("requested_in", "agent_1", "agent_2", NegotiationState.REQUESTED, {"role": "engineer"}),
            Negotiation("open_out", "agent_2", "agent_3", NegotiationState.OPEN, {"role": "designer"}),
            Negotiation("closed_in", "agent_4", "agent_2", NegotiationState.CLOSED, {"role": "manager"}),
        ]
    )
    events = InMemoryEvents(
        [
            ProtocolEvent(
                type=ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
                actor_agent_id="agent_1",
                negotiation_id="requested_in",
                occurred_at=datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc),
                payload={"subject": {"role": "engineer"}},
            ),
            ProtocolEvent(
                type=ProtocolEventType.MESSAGE,
                actor_agent_id="agent_3",
                negotiation_id="open_out",
                occurred_at=datetime(2026, 1, 7, 12, 5, tzinfo=timezone.utc),
                payload={"body": "Can discuss tomorrow."},
            ),
        ]
    )
    service = NegotiationService(
        connections=UnusedConnections(),
        negotiations=negotiations,
        events=events,
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 7, tzinfo=timezone.utc),
    )

    context = service.get_agent_decision_context(agent_id="agent_2", recent_event_limit=5)

    assert context == {
        "agent_id": "agent_2",
        "active_load": 2,
        "inbound_requested_negotiations": [
            {
                "id": "requested_in",
                "from_agent_id": "agent_1",
                "to_agent_id": "agent_2",
                "state": "requested",
                "subject": {"role": "engineer"},
            }
        ],
        "open_negotiations": [
            {
                "id": "open_out",
                "from_agent_id": "agent_2",
                "to_agent_id": "agent_3",
                "state": "open",
                "subject": {"role": "designer"},
            }
        ],
        "recent_events": [
            {
                "type": "open_negotiation_request",
                "actor_agent_id": "agent_1",
                "negotiation_id": "requested_in",
                "occurred_at": "2026-01-07T12:00:00+00:00",
                "payload": {"subject": {"role": "engineer"}},
            },
            {
                "type": "message",
                "actor_agent_id": "agent_3",
                "negotiation_id": "open_out",
                "occurred_at": "2026-01-07T12:05:00+00:00",
                "payload": {"body": "Can discuss tomorrow."},
            },
        ],
    }
    assert not negotiations.add_called
    assert not negotiations.save_called
    assert not events.append_called
