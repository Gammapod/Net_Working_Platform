from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from net_working_platform.application.negotiations import NegotiationService
from net_working_platform.domain.model import (
    AgentConnection,
    FactKind,
    Negotiation,
    NegotiationState,
    ProtocolEvent,
    ProtocolEventType,
    ProtocolViolation,
    RepresentedPartyFact,
    RepresentedPartyProfile,
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

    def list_active_for_agent(self, agent_id: str) -> list[Negotiation]:
        return [negotiation for negotiation in self.records.values() if agent_id in {negotiation.from_agent_id, negotiation.to_agent_id}]

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

    def list_recent_for_agent(self, agent_id: str, negotiation_ids: list[str], limit: int) -> list[ProtocolEvent]:
        del agent_id
        return [event for event in self.records if event.negotiation_id in negotiation_ids][-limit:]


def client_profile() -> RepresentedPartyProfile:
    return RepresentedPartyProfile(
        represented_party_id="client",
        represented_party_type="client",
        facts={
            "salary_range": RepresentedPartyFact(
                kind=FactKind.CONSTRAINT,
                label="Desired salary range",
                value={"min": 140000, "max": 170000, "currency": "USD"},
            ),
            "career_path": RepresentedPartyFact(
                kind=FactKind.EVIDENCE,
                label="Desired career path",
                value={"trajectory": "senior backend IC to staff engineer"},
            ),
        },
        priorities=(
            {"field": "salary_range", "rank": 1, "importance": "hard"},
            {"field": "career_path", "rank": 2, "importance": "strong"},
        ),
    )


def make_service(events: InMemoryEvents | None = None) -> NegotiationService:
    return NegotiationService(
        connections=UnusedConnections(),
        negotiations=InMemoryNegotiations(
            {
                "negotiation_1": Negotiation(
                    id="negotiation_1",
                    from_agent_id="client_agent",
                    to_agent_id="principal_agent",
                    state=NegotiationState.OPEN,
                    subject={"client_id": "client", "principal_id": "principal"},
                )
            }
        ),
        events=events or InMemoryEvents(),
        represented_party_profiles_by_agent={"client_agent": [client_profile()]},
        new_id=lambda: "unused",
        now=lambda: datetime(2026, 1, 9, 12, 0, tzinfo=timezone.utc),
    )


def test_disclose_facts_appends_structured_fact_events() -> None:
    """Protects INV-F-001."""
    events = InMemoryEvents()
    service = make_service(events)

    service.disclose_facts(
        negotiation_id="negotiation_1",
        actor_agent_id="client_agent",
        fields=["salary_range", "career_path"],
    )

    assert events.records == [
        ProtocolEvent(
            type=ProtocolEventType.FACT_DISCLOSED,
            actor_agent_id="client_agent",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 9, 12, 0, tzinfo=timezone.utc),
            payload={
                "represented_party_id": "client",
                "represented_party_type": "client",
                "field": "salary_range",
                "kind": "constraint",
                "label": "Desired salary range",
                "value": {"min": 140000, "max": 170000, "currency": "USD"},
            },
        ),
        ProtocolEvent(
            type=ProtocolEventType.FACT_DISCLOSED,
            actor_agent_id="client_agent",
            negotiation_id="negotiation_1",
            occurred_at=datetime(2026, 1, 9, 12, 0, tzinfo=timezone.utc),
            payload={
                "represented_party_id": "client",
                "represented_party_type": "client",
                "field": "career_path",
                "kind": "evidence",
                "label": "Desired career path",
                "value": {"trajectory": "senior backend IC to staff engineer"},
            },
        ),
    ]


def test_disclose_fact_rejects_unknown_or_unrepresented_field() -> None:
    """Protects INV-F-001."""
    events = InMemoryEvents()
    service = make_service(events)

    with pytest.raises(PermissionError):
        service.disclose_facts(
            negotiation_id="negotiation_1",
            actor_agent_id="principal_agent",
            fields=["salary_range"],
        )

    with pytest.raises(ProtocolViolation, match="unknown represented-party fact"):
        service.disclose_facts(
            negotiation_id="negotiation_1",
            actor_agent_id="client_agent",
            fields=["not_real"],
        )

    assert events.records == []


def test_fact_field_is_disclosed_at_most_once_per_negotiation() -> None:
    """Protects INV-F-003."""
    events = InMemoryEvents()
    service = make_service(events)

    service.disclose_facts(
        negotiation_id="negotiation_1",
        actor_agent_id="client_agent",
        fields=["salary_range"],
    )

    with pytest.raises(ProtocolViolation, match="already disclosed"):
        service.disclose_facts(
            negotiation_id="negotiation_1",
            actor_agent_id="client_agent",
            fields=["salary_range"],
        )

    assert len(events.records) == 1


def test_fact_disclosure_does_not_consume_message_budget() -> None:
    """Protects INV-F-002 and INV-N-008."""
    events = InMemoryEvents()
    service = make_service(events)

    service.disclose_facts(
        negotiation_id="negotiation_1",
        actor_agent_id="client_agent",
        fields=["salary_range"],
    )
    for index in range(3):
        service.send_message(
            negotiation_id="negotiation_1",
            actor_agent_id="client_agent",
            body=f"message {index}",
        )

    with pytest.raises(ProtocolViolation, match="message quota"):
        service.send_message(
            negotiation_id="negotiation_1",
            actor_agent_id="client_agent",
            body="quota exhausted after three messages, not after disclosure",
        )

    assert [event.type for event in events.records] == [
        ProtocolEventType.FACT_DISCLOSED,
        ProtocolEventType.MESSAGE,
        ProtocolEventType.MESSAGE,
        ProtocolEventType.MESSAGE,
    ]


def test_agent_decision_context_exposes_available_and_disclosed_facts() -> None:
    """Protects INV-F-001 and INV-H-004."""
    events = InMemoryEvents()
    service = make_service(events)
    service.disclose_facts(
        negotiation_id="negotiation_1",
        actor_agent_id="client_agent",
        fields=["salary_range"],
    )

    context = service.get_agent_decision_context(agent_id="client_agent")

    assert context["valid_next_actions_by_negotiation"]["negotiation_1"] == [
        "send_message",
        "propose_match",
        "close_negotiation",
    ]
    assert context["available_fact_disclosures_by_negotiation"] == {
        "negotiation_1": [
            {
                "represented_party_id": "client",
                "represented_party_type": "client",
                "field": "career_path",
                "kind": "evidence",
                "label": "Desired career path",
                "priority": {"field": "career_path", "rank": 2, "importance": "strong"},
            }
        ]
    }
    assert context["disclosed_facts_by_negotiation"] == {
        "negotiation_1": [
            {
                "represented_party_id": "client",
                "represented_party_type": "client",
                "field": "salary_range",
                "kind": "constraint",
                "label": "Desired salary range",
                "value": {"min": 140000, "max": 170000, "currency": "USD"},
            }
        ]
    }
