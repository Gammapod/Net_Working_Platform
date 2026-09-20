from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Protocol

from net_working_platform.domain.model import (
    AgentConnection,
    CapacityLimitExceeded,
    Negotiation,
    NegotiationDecision,
    NegotiationState,
    ProtocolEvent,
    ProtocolEventType,
    can_open_negotiation,
    ensure_negotiation_actor_is_participant,
    ensure_can_request_negotiation,
    next_negotiation_state,
)


class AgentConnectionRepository(Protocol):
    def get_between(self, from_agent_id: str, to_agent_id: str) -> AgentConnection | None: ...


class NegotiationRepository(Protocol):
    def count_open_for_agent(self, agent_id: str) -> int: ...

    def list_active_for_agent(self, agent_id: str) -> list[Negotiation]: ...

    def add(self, negotiation: Negotiation) -> None: ...

    def get(self, negotiation_id: str) -> Negotiation: ...

    def save(self, negotiation: Negotiation) -> None: ...


class ProtocolEventRepository(Protocol):
    def append(self, event: ProtocolEvent) -> None: ...

    def list_for_negotiation(self, negotiation_id: str) -> list[ProtocolEvent]: ...

    def list_recent_for_agent(self, agent_id: str, negotiation_ids: list[str], limit: int) -> list[ProtocolEvent]: ...


class NegotiationService:
    def __init__(
        self,
        *,
        connections: AgentConnectionRepository,
        negotiations: NegotiationRepository,
        events: ProtocolEventRepository,
        new_id: Callable[[], str],
        now: Callable[[], datetime],
    ) -> None:
        self._connections = connections
        self._negotiations = negotiations
        self._events = events
        self._new_id = new_id
        self._now = now

    def request_negotiation(
        self,
        *,
        from_agent_id: str,
        to_agent_id: str,
        subject: dict[str, object],
        max_open_negotiations: int,
    ) -> Negotiation:
        connection = self._connections.get_between(from_agent_id, to_agent_id)
        if connection is None:
            raise PermissionError("agent-agent connection must exist")
        ensure_can_request_negotiation(connection)

        try:
            can_open_negotiation(
                open_negotiation_count=self._negotiations.count_open_for_agent(from_agent_id),
                max_open_negotiations=max_open_negotiations,
            )
        except CapacityLimitExceeded:
            self._events.append(
                ProtocolEvent(
                    type=ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
                    actor_agent_id=from_agent_id,
                    negotiation_id=None,
                    occurred_at=self._now(),
                    payload={"to_agent_id": to_agent_id, "rejected": True, "reason": "capacity_limit"},
                )
            )
            raise

        negotiation = Negotiation(
            id=self._new_id(),
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            state=NegotiationState.REQUESTED,
            subject=subject,
        )
        self._negotiations.add(negotiation)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
                actor_agent_id=from_agent_id,
                negotiation_id=negotiation.id,
                occurred_at=self._now(),
                payload={"to_agent_id": to_agent_id, "subject": subject},
            )
        )
        return negotiation

    def respond_to_negotiation(
        self,
        *,
        negotiation_id: str,
        actor_agent_id: str,
        decision: NegotiationDecision,
    ) -> Negotiation:
        negotiation = self._negotiations.get(negotiation_id)
        ensure_negotiation_actor_is_participant(negotiation, actor_agent_id)
        next_state = next_negotiation_state(
            negotiation.state,
            ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
            decision=decision,
        )
        updated = replace(negotiation, state=next_state)
        self._negotiations.save(updated)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
                actor_agent_id=actor_agent_id,
                negotiation_id=negotiation_id,
                occurred_at=self._now(),
                payload={"decision": decision.value},
            )
        )
        return updated

    def send_message(self, *, negotiation_id: str, actor_agent_id: str, body: str) -> None:
        negotiation = self._negotiations.get(negotiation_id)
        ensure_negotiation_actor_is_participant(negotiation, actor_agent_id)
        next_negotiation_state(negotiation.state, ProtocolEventType.MESSAGE)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.MESSAGE,
                actor_agent_id=actor_agent_id,
                negotiation_id=negotiation_id,
                occurred_at=self._now(),
                payload={"body": body},
            )
        )

    def propose_match(
        self,
        *,
        negotiation_id: str,
        actor_agent_id: str,
        proposal: dict[str, object],
    ) -> None:
        negotiation = self._negotiations.get(negotiation_id)
        ensure_negotiation_actor_is_participant(negotiation, actor_agent_id)
        next_negotiation_state(negotiation.state, ProtocolEventType.MATCH_PROPOSED)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.MATCH_PROPOSED,
                actor_agent_id=actor_agent_id,
                negotiation_id=negotiation_id,
                occurred_at=self._now(),
                payload={"proposal": proposal},
            )
        )

    def accept_match(self, *, negotiation_id: str, actor_agent_id: str) -> Negotiation:
        negotiation = self._negotiations.get(negotiation_id)
        ensure_negotiation_actor_is_participant(negotiation, actor_agent_id)
        history = self._events.list_for_negotiation(negotiation_id)
        has_match_proposal = any(event.type == ProtocolEventType.MATCH_PROPOSED for event in history)
        next_state = next_negotiation_state(
            negotiation.state,
            ProtocolEventType.MATCH_ACCEPTED,
            has_match_proposal=has_match_proposal,
        )
        updated = replace(negotiation, state=next_state)
        self._negotiations.save(updated)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.MATCH_ACCEPTED,
                actor_agent_id=actor_agent_id,
                negotiation_id=negotiation_id,
                occurred_at=self._now(),
                payload={},
            )
        )
        return updated

    def close_negotiation(self, *, negotiation_id: str, actor_agent_id: str, reason: str) -> Negotiation:
        negotiation = self._negotiations.get(negotiation_id)
        ensure_negotiation_actor_is_participant(negotiation, actor_agent_id)
        next_state = next_negotiation_state(negotiation.state, ProtocolEventType.CLOSE_NEGOTIATION)
        updated = replace(negotiation, state=next_state)
        self._negotiations.save(updated)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.CLOSE_NEGOTIATION,
                actor_agent_id=actor_agent_id,
                negotiation_id=negotiation_id,
                occurred_at=self._now(),
                payload={"reason": reason},
            )
        )
        return updated

    def get_negotiation_history(self, negotiation_id: str) -> list[ProtocolEvent]:
        return self._events.list_for_negotiation(negotiation_id)

    def get_agent_decision_context(self, *, agent_id: str, recent_event_limit: int = 20) -> dict[str, object]:
        active_negotiations = self._negotiations.list_active_for_agent(agent_id)
        negotiation_ids = [negotiation.id for negotiation in active_negotiations]
        recent_events = self._events.list_recent_for_agent(agent_id, negotiation_ids, recent_event_limit)

        return {
            "agent_id": agent_id,
            "active_load": self._negotiations.count_open_for_agent(agent_id),
            "inbound_requested_negotiations": [
                _negotiation_to_context_record(negotiation)
                for negotiation in active_negotiations
                if negotiation.to_agent_id == agent_id and negotiation.state == NegotiationState.REQUESTED
            ],
            "open_negotiations": [
                _negotiation_to_context_record(negotiation)
                for negotiation in active_negotiations
                if negotiation.state == NegotiationState.OPEN
            ],
            "recent_events": [_event_to_context_record(event) for event in recent_events],
        }


def _negotiation_to_context_record(negotiation: Negotiation) -> dict[str, object]:
    return {
        "id": negotiation.id,
        "from_agent_id": negotiation.from_agent_id,
        "to_agent_id": negotiation.to_agent_id,
        "state": negotiation.state.value,
        "subject": negotiation.subject,
    }


def _event_to_context_record(event: ProtocolEvent) -> dict[str, object]:
    return {
        "type": event.type.value,
        "actor_agent_id": event.actor_agent_id,
        "negotiation_id": event.negotiation_id,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }
