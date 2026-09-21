from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NodeType(StrEnum):
    AGENT = "agent"
    CLIENT = "client"
    PRINCIPAL = "principal"


class AgentConnectionState(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAVORITE = "favorite"


class RepresentationState(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class NegotiationState(StrEnum):
    REQUESTED = "requested"
    OPEN = "open"
    PROPOSAL_PENDING = "proposal_pending"
    MATCHED = "matched"
    CLOSED = "closed"


class NegotiationDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class ProtocolEventType(StrEnum):
    OPEN_NEGOTIATION_REQUEST = "open_negotiation_request"
    OPEN_NEGOTIATION_RESPONSE = "open_negotiation_response"
    MESSAGE = "message"
    FACT_DISCLOSED = "fact_disclosed"
    MATCH_PROPOSED = "match_proposed"
    MATCH_ACCEPTED = "match_accepted"
    CLOSE_NEGOTIATION = "close_negotiation"


class FactKind(StrEnum):
    CONSTRAINT = "constraint"
    EVIDENCE = "evidence"


@dataclass(frozen=True)
class Node:
    id: str
    type: NodeType


@dataclass(frozen=True)
class AgentConnection:
    from_agent_id: str
    to_agent_id: str
    state: AgentConnectionState
    edge_kind: str = "agent_connection"


@dataclass(frozen=True)
class RepresentationEdge:
    agent_id: str
    represented_node_id: str
    represented_node_type: NodeType
    state: RepresentationState
    edge_kind: str = "representation"


@dataclass(frozen=True)
class Negotiation:
    id: str
    from_agent_id: str
    to_agent_id: str
    state: NegotiationState
    subject: dict[str, object]


@dataclass(frozen=True)
class ProtocolEvent:
    type: ProtocolEventType
    actor_agent_id: str
    negotiation_id: str | None
    occurred_at: datetime
    payload: dict[str, object]


@dataclass(frozen=True)
class RepresentedPartyFact:
    kind: FactKind
    label: str
    value: object


@dataclass(frozen=True)
class RepresentedPartyProfile:
    represented_party_id: str
    represented_party_type: str
    facts: dict[str, RepresentedPartyFact]
    priorities: tuple[dict[str, object], ...] = ()


class ProtocolViolation(ValueError):
    pass


class CapacityLimitExceeded(ProtocolViolation):
    pass


def ensure_can_request_negotiation(connection: AgentConnection) -> None:
    """INV-G-001: agent negotiation requests require an active connection."""
    if connection.state != AgentConnectionState.ACTIVE:
        raise PermissionError("agent-agent connection must be active")


def can_open_negotiation(open_negotiation_count: int, max_open_negotiations: int) -> bool:
    """INV-C-001: open negotiation limit is enforced."""
    if open_negotiation_count >= max_open_negotiations:
        raise CapacityLimitExceeded("open negotiation limit reached")
    return True


def can_append_message(state: NegotiationState) -> bool:
    """INV-N-004: Messages require an open negotiation."""
    return state in {NegotiationState.OPEN, NegotiationState.PROPOSAL_PENDING}


def ensure_negotiation_actor_is_participant(negotiation: Negotiation, actor_agent_id: str) -> None:
    """INV-N-007: Negotiation actions require a participant actor."""
    if actor_agent_id not in {negotiation.from_agent_id, negotiation.to_agent_id}:
        raise PermissionError("actor must be a negotiation participant")


def next_negotiation_state(
    current_state: NegotiationState | None,
    event_type: ProtocolEventType,
    *,
    decision: NegotiationDecision | None = None,
    has_match_proposal: bool = False,
) -> NegotiationState:
    if current_state is None:
        if event_type == ProtocolEventType.OPEN_NEGOTIATION_REQUEST:
            return NegotiationState.REQUESTED
        raise ProtocolViolation("negotiation must start with open_negotiation_request")

    if current_state in {NegotiationState.CLOSED, NegotiationState.MATCHED}:
        raise ProtocolViolation(f"{current_state.value} negotiation is terminal")

    if current_state == NegotiationState.REQUESTED:
        if event_type != ProtocolEventType.OPEN_NEGOTIATION_RESPONSE:
            raise ProtocolViolation("requested negotiation requires open_negotiation_response")
        if decision == NegotiationDecision.ACCEPT:
            return NegotiationState.OPEN
        if decision == NegotiationDecision.REJECT:
            return NegotiationState.CLOSED
        raise ProtocolViolation("open_negotiation_response requires accept or reject decision")

    if current_state == NegotiationState.OPEN:
        if event_type == ProtocolEventType.MESSAGE:
            return NegotiationState.OPEN
        if event_type == ProtocolEventType.FACT_DISCLOSED:
            return NegotiationState.OPEN
        if event_type == ProtocolEventType.MATCH_PROPOSED:
            return NegotiationState.PROPOSAL_PENDING
        if event_type == ProtocolEventType.MATCH_ACCEPTED:
            raise ProtocolViolation("match_acceptance requires pending match proposal")
        if event_type == ProtocolEventType.CLOSE_NEGOTIATION:
            return NegotiationState.CLOSED
        raise ProtocolViolation(f"{event_type.value} is not valid for open negotiation")

    if current_state == NegotiationState.PROPOSAL_PENDING:
        if event_type == ProtocolEventType.FACT_DISCLOSED:
            return NegotiationState.PROPOSAL_PENDING
        if event_type == ProtocolEventType.MESSAGE:
            return NegotiationState.OPEN
        if event_type == ProtocolEventType.MATCH_ACCEPTED:
            return NegotiationState.MATCHED
        if event_type == ProtocolEventType.CLOSE_NEGOTIATION:
            return NegotiationState.CLOSED
        if event_type == ProtocolEventType.MATCH_PROPOSED:
            raise ProtocolViolation("pending proposal must be resolved before another proposal")
        raise ProtocolViolation(f"{event_type.value} is not valid for proposal pending negotiation")

    raise ProtocolViolation(f"unknown negotiation state: {current_state}")
