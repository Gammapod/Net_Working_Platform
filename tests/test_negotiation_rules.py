import pytest

from net_working_platform.domain.model import (
    NegotiationDecision,
    NegotiationState,
    ProtocolEventType,
    ProtocolViolation,
    next_negotiation_state,
)


def test_open_negotiation_request_creates_requested_state() -> None:
    """Protects INV-N-001 and INV-N-002."""
    assert next_negotiation_state(None, ProtocolEventType.OPEN_NEGOTIATION_REQUEST) == NegotiationState.REQUESTED


def test_accept_requested_negotiation_opens() -> None:
    """Protects INV-N-003."""
    assert (
        next_negotiation_state(
            NegotiationState.REQUESTED,
            ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
            decision=NegotiationDecision.ACCEPT,
        )
        == NegotiationState.OPEN
    )


def test_reject_requested_negotiation_closes() -> None:
    """Protects INV-N-003."""
    assert (
        next_negotiation_state(
            NegotiationState.REQUESTED,
            ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
            decision=NegotiationDecision.REJECT,
        )
        == NegotiationState.CLOSED
    )


def test_message_keeps_open_negotiation_open() -> None:
    """Protects INV-N-004."""
    assert next_negotiation_state(NegotiationState.OPEN, ProtocolEventType.MESSAGE) == NegotiationState.OPEN


def test_message_requires_open_negotiation() -> None:
    """Protects INV-N-004."""
    with pytest.raises(ProtocolViolation):
        next_negotiation_state(NegotiationState.REQUESTED, ProtocolEventType.MESSAGE)


def test_match_proposal_keeps_negotiation_open() -> None:
    """Protects INV-N-005."""
    assert next_negotiation_state(NegotiationState.OPEN, ProtocolEventType.MATCH_PROPOSED) == NegotiationState.OPEN


def test_match_acceptance_requires_prior_proposal() -> None:
    """Protects INV-N-005."""
    with pytest.raises(ProtocolViolation):
        next_negotiation_state(
            NegotiationState.OPEN,
            ProtocolEventType.MATCH_ACCEPTED,
            has_match_proposal=False,
        )


def test_match_acceptance_closes_as_matched_after_proposal() -> None:
    """Protects INV-N-005."""
    assert (
        next_negotiation_state(
            NegotiationState.OPEN,
            ProtocolEventType.MATCH_ACCEPTED,
            has_match_proposal=True,
        )
        == NegotiationState.MATCHED
    )


def test_closed_negotiation_rejects_messages() -> None:
    """Protects INV-N-006."""
    with pytest.raises(ProtocolViolation):
        next_negotiation_state(NegotiationState.CLOSED, ProtocolEventType.MESSAGE)


def test_matched_negotiation_rejects_close() -> None:
    """Protects INV-N-006."""
    with pytest.raises(ProtocolViolation):
        next_negotiation_state(NegotiationState.MATCHED, ProtocolEventType.CLOSE_NEGOTIATION)
