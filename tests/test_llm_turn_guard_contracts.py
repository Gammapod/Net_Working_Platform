from __future__ import annotations

from scripts.dev.run_pairwise_strategy_experiment import (
    _validate_action_available,
    _validate_focus,
)


def test_llm_turn_guard_rejects_wrong_actor_focus_before_execution() -> None:
    """Protects INV-L-004 by rejecting a globally valid decision for the wrong scheduled actor."""
    validation = _validate_focus(
        raw_decision={
            "action": "send_message",
            "actor_agent_id": "agent_2",
            "negotiation_id": "negotiation_1",
            "body": "Wrong actor.",
        },
        expected_actor_agent_id="agent_1",
        expected_negotiation_id="negotiation_1",
        validation={"valid": True, "action": "send_message"},
    )

    assert validation == {
        "valid": False,
        "action": "send_message",
        "error": {
            "type": "FocusMismatch",
            "message": "decision actor_agent_id must be agent_1",
            "expected_actor_agent_id": "agent_1",
            "actual_actor_agent_id": "agent_2",
        },
    }


def test_llm_turn_guard_rejects_wrong_negotiation_focus_before_execution() -> None:
    """Protects INV-L-004 by rejecting a globally valid decision for the wrong negotiation."""
    validation = _validate_focus(
        raw_decision={
            "action": "send_message",
            "actor_agent_id": "agent_1",
            "negotiation_id": "negotiation_2",
            "body": "Wrong negotiation.",
        },
        expected_actor_agent_id="agent_1",
        expected_negotiation_id="negotiation_1",
        validation={"valid": True, "action": "send_message"},
    )

    assert validation == {
        "valid": False,
        "action": "send_message",
        "error": {
            "type": "FocusMismatch",
            "message": "decision negotiation_id must be negotiation_1",
            "expected_negotiation_id": "negotiation_1",
            "actual_negotiation_id": "negotiation_2",
        },
    }


def test_llm_turn_guard_rejects_action_unavailable_in_context() -> None:
    """Protects INV-L-004 by requiring a decision action to be context-valid before execution."""
    validation = _validate_action_available(
        raw_decision={"action": "defer", "actor_agent_id": "agent_1", "reason": "Wait."},
        context_package={
            "decision_context": {
                "valid_next_actions_by_negotiation": {
                    "negotiation_1": ["send_message", "close_negotiation"],
                }
            }
        },
        expected_negotiation_id="negotiation_1",
        validation={"valid": True, "action": "defer"},
    )

    assert validation == {
        "valid": False,
        "action": "defer",
        "error": {
            "type": "ActionUnavailable",
            "message": "decision action must be valid for negotiation negotiation_1",
            "expected_negotiation_id": "negotiation_1",
            "valid_actions": ["send_message", "close_negotiation"],
            "actual_action": "defer",
        },
    }
