from __future__ import annotations

import pytest

from net_working_platform.application.llm_decisions import (
    LlmDecisionAction,
    LlmDecisionValidationError,
    parse_llm_decision,
)


def test_parse_llm_accept_negotiation_decision() -> None:
    """Protects INV-L-001 and INV-L-002."""
    decision = parse_llm_decision(
        {
            "action": "accept_negotiation",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_2",
        }
    )

    assert decision.action == LlmDecisionAction.ACCEPT_NEGOTIATION
    assert decision.payload == {
        "negotiation_id": "negotiation_1",
        "actor_agent_id": "agent_2",
    }


def test_parse_llm_decision_rejects_unknown_action() -> None:
    """Protects INV-L-001."""
    with pytest.raises(LlmDecisionValidationError, match="unsupported action"):
        parse_llm_decision(
            {
                "action": "delete_database",
                "actor_agent_id": "agent_2",
            }
        )


def test_parse_llm_decision_requires_action_specific_fields() -> None:
    """Protects INV-L-002."""
    with pytest.raises(LlmDecisionValidationError, match="missing required field: body"):
        parse_llm_decision(
            {
                "action": "send_message",
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
            }
        )

    with pytest.raises(LlmDecisionValidationError, match="field proposal must be object"):
        parse_llm_decision(
            {
                "action": "propose_match",
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "proposal": "not an object",
            }
        )


def test_parse_llm_decision_rejects_extra_fields() -> None:
    """Protects INV-L-002."""
    with pytest.raises(LlmDecisionValidationError, match="unexpected field: command"):
        parse_llm_decision(
            {
                "action": "accept_negotiation",
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "command": "run arbitrary shell",
            }
        )


def test_parse_llm_defer_decision() -> None:
    """Protects INV-L-003."""
    decision = parse_llm_decision(
        {
            "action": "defer",
            "actor_agent_id": "agent_2",
            "reason": "needs_more_information",
        }
    )

    assert decision.action == LlmDecisionAction.DEFER
    assert decision.payload == {
        "actor_agent_id": "agent_2",
        "reason": "needs_more_information",
    }
