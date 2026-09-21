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
    ProtocolViolation,
    RepresentedPartyProfile,
    can_open_negotiation,
    ensure_negotiation_actor_is_participant,
    ensure_can_request_negotiation,
    next_negotiation_state,
)


SUPPORTED_PROTOCOL_ACTIONS = [
    "accept_negotiation",
    "reject_negotiation",
    "send_message",
    "propose_match",
    "accept_match",
    "close_negotiation",
    "defer",
]
MAX_MESSAGES_PER_AGENT_PER_NEGOTIATION = 3


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
        represented_party_profiles_by_agent: dict[str, list[RepresentedPartyProfile]] | None = None,
    ) -> None:
        self._connections = connections
        self._negotiations = negotiations
        self._events = events
        self._new_id = new_id
        self._now = now
        self._represented_party_profiles_by_agent = represented_party_profiles_by_agent or {}

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
        history = self._events.list_for_negotiation(negotiation_id)
        if _message_count_for_actor(history, actor_agent_id) >= MAX_MESSAGES_PER_AGENT_PER_NEGOTIATION:
            raise ProtocolViolation("message quota exhausted for actor in negotiation")
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.MESSAGE,
                actor_agent_id=actor_agent_id,
                negotiation_id=negotiation_id,
                occurred_at=self._now(),
                payload={"body": body},
            )
        )

    def disclose_facts(
        self,
        *,
        negotiation_id: str,
        actor_agent_id: str,
        fields: list[str],
    ) -> None:
        if not fields:
            return
        negotiation = self._negotiations.get(negotiation_id)
        ensure_negotiation_actor_is_participant(negotiation, actor_agent_id)
        next_negotiation_state(negotiation.state, ProtocolEventType.FACT_DISCLOSED)
        history = self._events.list_for_negotiation(negotiation_id)

        if not self._represented_party_profiles_by_agent.get(actor_agent_id):
            raise PermissionError("actor does not represent any party with fact profiles")

        if len(set(fields)) != len(fields):
            raise ProtocolViolation("represented-party fact already disclosed in decision")

        disclosures = []
        for field in fields:
            disclosure = self._fact_disclosure_for_actor_field(actor_agent_id, field)
            if disclosure is None:
                raise ProtocolViolation("unknown represented-party fact")
            profile, fact = disclosure
            if _fact_already_disclosed(history, profile.represented_party_id, field):
                raise ProtocolViolation("represented-party fact already disclosed in negotiation")
            disclosures.append((profile, field, fact))

        for profile, field, fact in disclosures:
            self._events.append(
                ProtocolEvent(
                    type=ProtocolEventType.FACT_DISCLOSED,
                    actor_agent_id=actor_agent_id,
                    negotiation_id=negotiation_id,
                    occurred_at=self._now(),
                    payload={
                        "represented_party_id": profile.represented_party_id,
                        "represented_party_type": profile.represented_party_type,
                        "field": field,
                        "kind": fact.kind.value,
                        "label": fact.label,
                        "value": fact.value,
                    },
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

    def get_agent_decision_context(
        self,
        *,
        agent_id: str,
        recent_event_limit: int = 20,
        max_active_negotiations: int | None = None,
    ) -> dict[str, object]:
        active_negotiations = self._negotiations.list_active_for_agent(agent_id)
        negotiation_ids = [negotiation.id for negotiation in active_negotiations]
        recent_events = self._events.list_recent_for_agent(agent_id, negotiation_ids, recent_event_limit)
        active_load = self._negotiations.count_open_for_agent(agent_id)
        histories = {
            negotiation.id: self._events.list_for_negotiation(negotiation.id)
            for negotiation in active_negotiations
        }

        available_fact_disclosures = {
            negotiation.id: self._available_fact_disclosures(agent_id, histories[negotiation.id])
            for negotiation in active_negotiations
        }

        context: dict[str, object] = {
            "agent_id": agent_id,
            "active_load": active_load,
            "supported_protocol_actions": SUPPORTED_PROTOCOL_ACTIONS,
            "valid_next_actions_by_negotiation": {
                negotiation.id: _valid_next_actions_for_negotiation(
                    negotiation,
                    histories[negotiation.id],
                    agent_id,
                )
                for negotiation in active_negotiations
            },
            "message_budget_by_negotiation": {
                negotiation.id: _message_budget_for_negotiation(histories[negotiation.id], agent_id)
                for negotiation in active_negotiations
            },
            "available_fact_disclosures_by_negotiation": available_fact_disclosures,
            "disclosed_facts_by_negotiation": {
                negotiation.id: _disclosed_facts(histories[negotiation.id])
                for negotiation in active_negotiations
            },
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
        if max_active_negotiations is not None:
            context["max_active_negotiations"] = max_active_negotiations
            context["capacity_remaining"] = max(max_active_negotiations - active_load, 0)
        return context

    def _fact_disclosure_for_actor_field(self, actor_agent_id: str, field: str) -> tuple[RepresentedPartyProfile, object] | None:
        matches = [
            (profile, profile.facts[field])
            for profile in self._represented_party_profiles_by_agent.get(actor_agent_id, [])
            if field in profile.facts
        ]
        if len(matches) > 1:
            raise ProtocolViolation("ambiguous represented-party fact")
        return matches[0] if matches else None

    def _available_fact_disclosures(self, actor_agent_id: str, history: list[ProtocolEvent]) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for profile in self._represented_party_profiles_by_agent.get(actor_agent_id, []):
            priority_by_field = {
                str(priority.get("field")): priority
                for priority in profile.priorities
                if "field" in priority
            }
            for field, fact in profile.facts.items():
                if _fact_already_disclosed(history, profile.represented_party_id, field):
                    continue
                record: dict[str, object] = {
                    "represented_party_id": profile.represented_party_id,
                    "represented_party_type": profile.represented_party_type,
                    "field": field,
                    "kind": fact.kind.value,
                    "label": fact.label,
                }
                if field in priority_by_field:
                    record["priority"] = priority_by_field[field]
                records.append(record)
        return records


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


def _valid_next_actions_for_negotiation(
    negotiation: Negotiation,
    history: list[ProtocolEvent],
    actor_agent_id: str,
) -> list[str]:
    if negotiation.state == NegotiationState.REQUESTED:
        return ["accept_negotiation", "reject_negotiation"]

    if negotiation.state == NegotiationState.OPEN:
        has_match_proposal = any(event.type == ProtocolEventType.MATCH_PROPOSED for event in history)
        has_message_budget = _message_count_for_actor(history, actor_agent_id) < MAX_MESSAGES_PER_AGENT_PER_NEGOTIATION
        if has_match_proposal and not has_message_budget:
            return ["accept_match", "close_negotiation"]

        actions = []
        if has_message_budget:
            actions.append("send_message")
        actions.append("propose_match")
        if has_match_proposal:
            actions.append("accept_match")
        actions.append("close_negotiation")
        return actions

    return []


def _message_budget_for_negotiation(history: list[ProtocolEvent], actor_agent_id: str) -> dict[str, int]:
    messages_sent = _message_count_for_actor(history, actor_agent_id)
    return {
        "max_messages_per_agent": MAX_MESSAGES_PER_AGENT_PER_NEGOTIATION,
        "messages_sent_by_agent": messages_sent,
        "messages_remaining_for_agent": max(MAX_MESSAGES_PER_AGENT_PER_NEGOTIATION - messages_sent, 0),
    }


def _message_count_for_actor(history: list[ProtocolEvent], actor_agent_id: str) -> int:
    return sum(
        1
        for event in history
        if event.type == ProtocolEventType.MESSAGE and event.actor_agent_id == actor_agent_id
    )


def _fact_already_disclosed(history: list[ProtocolEvent], represented_party_id: str, field: str) -> bool:
    return any(
        event.type == ProtocolEventType.FACT_DISCLOSED
        and event.payload.get("represented_party_id") == represented_party_id
        and event.payload.get("field") == field
        for event in history
    )


def _disclosed_facts(history: list[ProtocolEvent]) -> list[dict[str, object]]:
    return [
        {
            "represented_party_id": str(event.payload["represented_party_id"]),
            "represented_party_type": str(event.payload["represented_party_type"]),
            "field": str(event.payload["field"]),
            "kind": str(event.payload["kind"]),
            "label": str(event.payload["label"]),
            "value": event.payload["value"],
        }
        for event in history
        if event.type == ProtocolEventType.FACT_DISCLOSED
    ]
