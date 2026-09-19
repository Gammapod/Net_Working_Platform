from net_working_platform.domain.model import NegotiationState, can_append_message


def test_domain_smoke() -> None:
    """Protects INV-H-001 test traceability wiring for initial skeleton."""
    assert can_append_message(NegotiationState.OPEN)
    assert not can_append_message(NegotiationState.REQUESTED)
